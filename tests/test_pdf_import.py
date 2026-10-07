import os
import shutil

import pymupdf
import pytest

from rosetta.errors import ImportProblem
from rosetta.flatten import flatten
from rosetta.loader import load_artwork
from rosetta.pdf_import import page_count, pdf_page_to_svg
from rosetta.svgdoc import normalize
from tests.helpers import shapes_bbox

MM = 72 / 25.4  # points per mm


@pytest.fixture
def sample_pdf(tmp_path):
    """Two pages. Page 1: a red 50 x 30 mm rect at (10 mm, 10 mm) on a 100 x 80 mm page, plus text."""
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=100 * MM, height=80 * MM)
    page.draw_rect(pymupdf.Rect(10 * MM, 10 * MM, 60 * MM, 40 * MM), color=(1, 0, 0), width=1)
    page.insert_text((10 * MM, 75 * MM), "Hi", fontsize=12)
    doc.new_page(width=100 * MM, height=80 * MM)
    doc.save(path)
    doc.close()
    return path


def _clip_pdf(tmp_path, stream: bytes):
    """A 300 x 300 pt page whose content stream is exactly `stream`."""
    path = tmp_path / "clip.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    page.draw_rect(pymupdf.Rect(0, 0, 1, 1))  # creates a contents stream to overwrite
    doc.update_stream(page.get_contents()[0], stream)
    doc.save(path)
    doc.close()
    return path


def test_page_count(sample_pdf):
    assert page_count(sample_pdf) == 2


def test_pdf_page_becomes_svg_in_points(sample_pdf):
    page = pdf_page_to_svg(sample_pdf, 0)
    assert page.has_text is True
    assert page.has_clip is False
    assert page.page_count == 2
    doc = normalize(page.svg.encode("utf-8"), source_hint="pdf")
    assert (doc.width_mm, doc.height_mm) == pytest.approx((100.0, 80.0), abs=0.01)
    red = [shape for shape in flatten(doc) if shape.color == "#ff0000"]
    assert shapes_bbox(red) == pytest.approx((10, 10, 60, 40), abs=0.05)


def test_rotated_page_is_drawn_as_displayed(tmp_path):
    path = tmp_path / "rotated.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=200 * MM, height=100 * MM)
    page.draw_rect(pymupdf.Rect(10 * MM, 10 * MM, 60 * MM, 40 * MM), color=(1, 0, 0), width=1)
    page.set_rotation(90)
    doc.save(path)
    doc.close()
    result = pdf_page_to_svg(path, 0)
    assert result.has_clip is False
    normalized = normalize(result.svg.encode("utf-8"), source_hint="pdf")
    assert (normalized.width_mm, normalized.height_mm) == pytest.approx((100.0, 200.0), abs=0.01)
    red = [shape for shape in flatten(normalized) if shape.color == "#ff0000"]
    assert shapes_bbox(red) == pytest.approx((60, 10, 90, 60), abs=0.05)


def test_ai_with_pdf_compatibility_opens(sample_pdf, tmp_path):
    ai_path = tmp_path / "drawing.ai"
    shutil.copy(sample_pdf, ai_path)
    assert "<svg" in pdf_page_to_svg(ai_path, 0).svg


def test_ai_without_pdf_compatibility_is_explained(tmp_path):
    ai_path = tmp_path / "old.ai"
    ai_path.write_bytes(b"%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator\n")
    with pytest.raises(ImportProblem, match="PDF Compatible"):
        pdf_page_to_svg(ai_path, 0)


def test_missing_page_is_explained(sample_pdf):
    with pytest.raises(ImportProblem, match="has 2 pages"):
        pdf_page_to_svg(sample_pdf, 5)


def test_missing_page_names_the_file_and_counts_from_1(sample_pdf):
    with pytest.raises(ImportProblem) as problem:
        pdf_page_to_svg(sample_pdf, 5)
    assert str(problem.value) == "sample.pdf has 2 pages; choose a page from 1 to 2."


def test_missing_page_of_a_one_page_pdf_is_singular(tmp_path):
    path = tmp_path / "single page.pdf"
    doc = pymupdf.open()
    doc.new_page(width=200, height=200).draw_line((10, 10), (100, 10))
    doc.save(path)
    doc.close()
    with pytest.raises(ImportProblem) as problem:
        pdf_page_to_svg(path, 1)
    assert str(problem.value) == "single page.pdf has 1 page; choose page 1."


def test_the_pdf_import_uses_the_svg_readers_public_parser():
    from rosetta import pdf_import, svgdoc

    assert pdf_import.SVG_PARSER is svgdoc.SVG_PARSER
    assert not hasattr(svgdoc, "_PARSER") and not hasattr(pdf_import, "_PARSER")


def test_negative_page_index_is_explained(sample_pdf):
    with pytest.raises(ImportProblem, match="choose a page from 1 to 2"):
        pdf_page_to_svg(sample_pdf, -1)


def test_password_protected_pdf_is_explained(tmp_path):
    path = tmp_path / "locked.pdf"
    doc = pymupdf.open()
    doc.new_page(width=200, height=200).draw_line((10, 10), (100, 10))
    doc.save(
        path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="student", owner_pw="teacher"
    )
    doc.close()
    with pytest.raises(ImportProblem, match="password"):
        pdf_page_to_svg(path, 0)
    with pytest.raises(ImportProblem, match="password"):
        page_count(path)


def test_svg_renamed_to_pdf_is_explained(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"/>')
    with pytest.raises(ImportProblem, match="isn't a PDF"):
        pdf_page_to_svg(path, 0)


def test_invisible_text_is_not_reported_as_text(tmp_path):
    path = tmp_path / "ocr.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20, 20), "OCR", render_mode=3)  # invisible, like an OCR text layer
    page.draw_line((10, 100), (150, 100))
    doc.save(path)
    doc.close()
    assert pdf_page_to_svg(path, 0).has_text is False


def test_clip_smaller_than_the_page_is_reported(tmp_path):
    path = _clip_pdf(tmp_path, b"q 50 50 100 100 re W n 1 0 0 RG 0 0 300 300 re S Q")
    assert pdf_page_to_svg(path, 0).has_clip is True


def test_page_sized_clip_is_not_reported(tmp_path):
    path = _clip_pdf(tmp_path, b"q 0 0 300 300 re W n 1 0 0 RG 10 10 100 100 re S Q")
    assert pdf_page_to_svg(path, 0).has_clip is False


def test_page_sized_clip_on_a_rotated_page_is_not_reported(tmp_path):
    path = tmp_path / "rotated-clip.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=200)
    page.draw_rect(pymupdf.Rect(0, 0, 1, 1))
    doc.update_stream(
        page.get_contents()[0], b"q 0 0 400 200 re W n 1 0 0 RG 10 10 100 100 re S Q"
    )
    page.set_rotation(90)
    doc.save(path)
    doc.close()
    assert pdf_page_to_svg(path, 0).has_clip is False


# A shape that is filled and stroked: MuPDF writes two paths (the fill, then the same outline stroked).
# Rosetta draws outlines only, so the pair must come out as one outline, in the stroke's color.

def _shape_pdf(tmp_path, draw, name="shape.pdf"):
    """A 100 x 80 mm page; draw(page) puts shapes on it."""
    path = tmp_path / name
    doc = pymupdf.open()
    draw(doc.new_page(width=100 * MM, height=80 * MM))
    doc.save(path)
    doc.close()
    return path


_BOX = pymupdf.Rect(10 * MM, 10 * MM, 60 * MM, 40 * MM)
BLACK, RED, BLUE, WHITE = (0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 1, 1)


def _codes(artwork):
    return {issue.code for issue in artwork.issues}


@pytest.mark.parametrize("draw_shape", [
    lambda page, **paint: page.draw_rect(_BOX, width=1, **paint),
    lambda page, **paint: page.draw_circle(pymupdf.Point(35 * MM, 25 * MM), 12 * MM, width=1, **paint),
], ids=["rectangle", "circle"])
def test_a_filled_and_stroked_shape_in_one_color_is_drawn_once(tmp_path, draw_shape):
    path = _shape_pdf(tmp_path, lambda page: draw_shape(page, color=BLACK, fill=BLACK))
    assert pdf_page_to_svg(path, 0).svg.count("<path") == 1
    art = load_artwork(path)
    shape, = art.shapes
    assert shape.stroked and shape.color == "#000000"
    outline, = shape.polylines
    assert outline[0] == pytest.approx(outline[-1])  # the one closed loop
    assert "fill_only" not in _codes(art)


def test_a_filled_and_stroked_shape_in_two_colors_is_drawn_in_the_stroke_color_only(tmp_path):
    path = _shape_pdf(tmp_path, lambda page: page.draw_rect(_BOX, color=RED, fill=BLUE, width=1))
    art = load_artwork(path)
    shape, = art.shapes
    assert (shape.color, shape.stroked) == ("#ff0000", True)  # no blue pen layer
    assert len(shape.polylines) == 1
    assert "fill_only" not in _codes(art)  # and no false "solid fills" warning


def test_a_white_filled_box_with_a_black_outline_is_just_the_outline(tmp_path):
    path = _shape_pdf(tmp_path, lambda page: page.draw_rect(_BOX, color=BLACK, fill=WHITE, width=1))
    art = load_artwork(path)
    shape, = art.shapes
    assert shape.color == "#000000"
    assert _codes(art).isdisjoint({"fill_only", "white"})  # the fill was not a separate white shape


def test_each_filled_and_stroked_shape_on_a_page_is_drawn_once(tmp_path):
    def draw(page):
        page.draw_rect(_BOX, color=BLACK, fill=BLACK, width=1)
        page.draw_rect(pymupdf.Rect(65 * MM, 10 * MM, 90 * MM, 40 * MM), color=RED, fill=BLUE, width=1)
        page.draw_rect(pymupdf.Rect(10 * MM, 50 * MM, 40 * MM, 70 * MM), color=BLACK, width=1)  # stroke only

    art = load_artwork(_shape_pdf(tmp_path, draw))
    assert sorted(shape.color for shape in art.shapes) == ["#000000", "#000000", "#ff0000"]
    assert all(len(shape.polylines) == 1 for shape in art.shapes)


def test_a_fill_without_an_outline_stays_and_its_outline_is_drawn_once(tmp_path):
    path = _shape_pdf(tmp_path, lambda page: page.draw_rect(_BOX, color=None, fill=BLUE))
    art = load_artwork(path)
    shape, = art.shapes
    assert (shape.color, shape.filled, shape.stroked) == ("#0000ff", True, False)
    assert len(shape.polylines) == 1
    assert "fill_only" in _codes(art)


def test_an_outline_is_kept_beside_a_fill_that_is_not_its_own(tmp_path):
    def draw(page):
        page.draw_rect(_BOX, color=None, fill=BLUE)  # a fill...
        page.draw_rect(pymupdf.Rect(20 * MM, 15 * MM, 50 * MM, 35 * MM), color=RED, width=1)  # ...with another shape's outline

    art = load_artwork(_shape_pdf(tmp_path, draw))
    assert sorted(shape.color for shape in art.shapes) == ["#0000ff", "#ff0000"]


def test_a_fill_under_a_white_outline_is_kept_because_white_is_skipped(tmp_path):
    path = _shape_pdf(tmp_path, lambda page: page.draw_rect(_BOX, color=WHITE, fill=BLACK, width=1))
    art = load_artwork(path)
    assert "#000000" in {shape.color for shape in art.shapes}  # the shape does not vanish


def test_big_embedded_picture_is_dropped_from_the_svg(tmp_path):
    path = tmp_path / "photo.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2000, 2000), False)
    pix.samples_mv[:] = os.urandom(len(pix.samples_mv))  # noise doesn't compress: ~12 MB of PNG
    page.insert_image(page.rect, pixmap=pix)
    page.draw_line((10, 10), (100, 100))
    doc.save(path)
    doc.close()
    result = pdf_page_to_svg(path, 0)
    assert "base64" not in result.svg
    assert "<image" in result.svg  # the tag stays, so EMS can report "Pictures can't be drawn"
