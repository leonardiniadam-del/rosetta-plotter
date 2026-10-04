import gzip
import pathlib
import shutil

import pymupdf
import pytest

from rosetta.errors import ImportProblem
from rosetta.loader import load_artwork
from tests import samples


def _two_page_pdf(path):
    doc = pymupdf.open()
    for _ in range(2):
        page = doc.new_page(width=200, height=200)
        page.draw_line((10, 10), (150, 10), color=(0, 0, 0))
    doc.save(path)
    doc.close()
    return path


def test_loads_svg(tmp_path):
    path = tmp_path / "logo.svg"
    path.write_bytes(samples.ILLUSTRATOR_EXPORT)
    art = load_artwork(path)
    assert art.name == "logo"
    assert (art.width_mm, art.height_mm) == pytest.approx((200, 100), abs=0.001)
    assert art.source == "illustrator"
    assert {issue.code for issue in art.issues} == {"fill_only"}
    assert len(art.shapes) == 2


def test_loads_pdf_with_text_issue(tmp_path):
    path = tmp_path / "page.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    page.draw_line((10, 10), (150, 10), color=(0, 0, 0))
    page.insert_text((10, 100), "Hi")
    doc.save(path)
    doc.close()
    art = load_artwork(path)
    assert art.name == "page"  # one-page PDFs keep the bare file name
    assert art.source == "pdf"
    assert "pdf_text" in {issue.code for issue in art.issues}


def test_affinity_native_file_is_explained(tmp_path):
    path = tmp_path / "drawing.afdesign"
    path.write_bytes(b"not really")
    with pytest.raises(ImportProblem, match="File › Export"):
        load_artwork(path)


def test_unsupported_extension_is_explained(tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(b"x")
    with pytest.raises(ImportProblem, match="SVG, PDF, or AI"):
        load_artwork(path)


def test_missing_file_is_explained(tmp_path):
    with pytest.raises(ImportProblem, match="can't be found"):
        load_artwork(tmp_path / "gone.svg")


def test_file_with_nothing_drawable_is_refused(tmp_path):
    path = tmp_path / "blank.svg"
    path.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"/>')
    with pytest.raises(ImportProblem, match="no lines to draw"):
        load_artwork(path)


def test_text_only_svg_is_explained_as_text(tmp_path):
    path = tmp_path / "words.svg"
    path.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"><text>Hi</text></svg>'
    )
    with pytest.raises(ImportProblem, match="convert text to outlines"):
        load_artwork(path)


def test_compressed_svg_is_explained(tmp_path):
    path = tmp_path / "logo.svgz"
    path.write_bytes(gzip.compress(samples.ILLUSTRATOR_EXPORT))
    with pytest.raises(ImportProblem, match="plain SVG"):
        load_artwork(path)


def test_unreadable_svg_is_explained(tmp_path, monkeypatch):
    path = tmp_path / "locked.svg"
    path.write_bytes(samples.ILLUSTRATOR_EXPORT)

    def deny(self):
        raise PermissionError("in use")

    monkeypatch.setattr(pathlib.Path, "read_bytes", deny)
    with pytest.raises(ImportProblem, match="couldn't read locked.svg"):
        load_artwork(path)


def test_unreadable_pdf_is_explained(tmp_path, monkeypatch):
    path = _two_page_pdf(tmp_path / "locked.pdf")

    def deny(*args, **kwargs):
        raise PermissionError("in use")

    monkeypatch.setattr("rosetta.loader.pdf_page_to_svg", deny)
    with pytest.raises(ImportProblem, match="couldn't read locked.pdf"):
        load_artwork(path)


def test_multi_page_pdf_names_the_page(tmp_path):
    path = _two_page_pdf(tmp_path / "plans.pdf")
    assert load_artwork(path, page=1).name == "plans (page 2)"
    assert load_artwork(path).name == "plans (page 1)"


def test_ai_with_pdf_compatibility_loads(tmp_path):
    pdf = _two_page_pdf(tmp_path / "plans.pdf")
    ai = tmp_path / "drawing.ai"
    shutil.copy(pdf, ai)
    art = load_artwork(ai)
    assert art.source == "pdf"
    assert len(art.shapes) == 1


def test_pdf_with_a_clipping_mask_gets_a_clip_issue(tmp_path):
    path = tmp_path / "masked.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    page.draw_rect(pymupdf.Rect(0, 0, 1, 1))
    doc.update_stream(
        page.get_contents()[0], b"q 50 50 100 100 re W n 1 0 0 RG 60 60 80 80 re S Q"
    )
    doc.save(path)
    doc.close()
    art = load_artwork(path)
    assert "clip" in {issue.code for issue in art.issues}


def test_pdf_content_outside_the_page_is_not_drawn(tmp_path):
    path = tmp_path / "overhang.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=100, height=100)
    page.draw_rect(pymupdf.Rect(-50, 10, 50, 50), color=(0, 0, 0))  # half off the left edge
    page.draw_line((-100, -100), (-50, -50), color=(1, 0, 0))  # entirely off the page
    doc.save(path)
    doc.close()
    art = load_artwork(path)
    xs = [x for shape in art.shapes for line in shape.polylines for x, _ in line]
    assert min(xs) == pytest.approx(0.0, abs=0.01)
    assert {shape.color for shape in art.shapes} == {"#000000"}


def test_svg_content_outside_the_artboard_is_kept(tmp_path):
    path = tmp_path / "overhang.svg"
    path.write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">'
        b'<line x1="-5" y1="5" x2="5" y2="5" stroke="black"/></svg>'
    )
    xs = [x for shape in load_artwork(path).shapes for line in shape.polylines for x, _ in line]
    assert min(xs) == pytest.approx(-5.0)
