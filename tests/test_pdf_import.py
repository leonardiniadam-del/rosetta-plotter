import shutil

import pymupdf
import pytest

from rosetta.errors import ImportProblem
from rosetta.flatten import flatten
from rosetta.pdf_import import page_count, pdf_page_to_svg
from rosetta.svgdoc import normalize
from tests.helpers import shapes_bbox

MM = 72 / 25.4  # points per mm


@pytest.fixture
def sample_pdf(tmp_path):
    """Two pages. Page 1: a red 50 mm square at (10 mm, 10 mm) on a 100 x 80 mm page, plus text."""
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=100 * MM, height=80 * MM)
    page.draw_rect(pymupdf.Rect(10 * MM, 10 * MM, 60 * MM, 60 * MM), color=(1, 0, 0), width=1)
    page.insert_text((10 * MM, 75 * MM), "Hi", fontsize=12)
    doc.new_page(width=100 * MM, height=80 * MM)
    doc.save(path)
    doc.close()
    return path


def test_page_count(sample_pdf):
    assert page_count(sample_pdf) == 2


def test_pdf_page_becomes_svg_in_points(sample_pdf):
    svg_text, has_text = pdf_page_to_svg(sample_pdf, 0)
    assert has_text is True
    doc = normalize(svg_text.encode("utf-8"), source_hint="pdf")
    assert (doc.width_mm, doc.height_mm) == pytest.approx((100.0, 80.0), abs=0.01)
    red = [shape for shape in flatten(doc) if shape.color == "#ff0000"]
    assert shapes_bbox(red) == pytest.approx((10, 10, 60, 60), abs=0.05)


def test_ai_with_pdf_compatibility_opens(sample_pdf, tmp_path):
    ai_path = tmp_path / "drawing.ai"
    shutil.copy(sample_pdf, ai_path)
    svg_text, _ = pdf_page_to_svg(ai_path, 0)
    assert "<svg" in svg_text


def test_ai_without_pdf_compatibility_is_explained(tmp_path):
    ai_path = tmp_path / "old.ai"
    ai_path.write_bytes(b"%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator\n")
    with pytest.raises(ImportProblem, match="PDF Compatible"):
        pdf_page_to_svg(ai_path, 0)


def test_missing_page_is_explained(sample_pdf):
    with pytest.raises(ImportProblem, match="has 2 pages"):
        pdf_page_to_svg(sample_pdf, 5)
