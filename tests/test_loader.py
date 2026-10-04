import pymupdf
import pytest

from rosetta.errors import ImportProblem
from rosetta.loader import load_artwork
from tests import samples


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
