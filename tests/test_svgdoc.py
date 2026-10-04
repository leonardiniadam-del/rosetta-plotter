import pytest

from rosetta.errors import ImportProblem
from rosetta.svgdoc import detect_source, normalize
from tests import samples


def test_detect_source():
    assert normalize(samples.ILLUSTRATOR_EXPORT).source == "illustrator"
    assert normalize(samples.ILLUSTRATOR_PX).source == "illustrator"
    assert normalize(samples.AFFINITY_EXPORT).source == "affinity"
    assert normalize(samples.INKSCAPE_MM).source == "inkscape"
    assert normalize(samples.GENERIC_PX).source == "svg"


def test_illustrator_viewbox_is_points():
    doc = normalize(samples.ILLUSTRATOR_EXPORT)
    assert doc.width_mm == pytest.approx(200.0, abs=0.001)
    assert doc.height_mm == pytest.approx(100.0, abs=0.001)


def test_illustrator_px_means_points():
    doc = normalize(samples.ILLUSTRATOR_PX)
    assert (doc.width_mm, doc.height_mm) == pytest.approx((215.9, 279.4))


def test_affinity_percent_falls_back_to_viewbox():
    doc = normalize(samples.AFFINITY_EXPORT)
    assert (doc.width_mm, doc.height_mm) == pytest.approx((100.0, 50.0), abs=0.001)


def test_inkscape_mm_kept():
    doc = normalize(samples.INKSCAPE_MM)
    assert (doc.width_mm, doc.height_mm) == pytest.approx((100.0, 50.0))


def test_generic_without_viewbox_gets_one():
    doc = normalize(samples.GENERIC_PX)
    assert (doc.width_mm, doc.height_mm) == pytest.approx((25.4, 12.7))
    assert doc.root.get("viewBox") == "0.000000 0.000000 96.000000 48.000000"


def test_root_rewritten_in_mm():
    doc = normalize(samples.ILLUSTRATOR_EXPORT)
    assert doc.root.get("width") == "200.000000mm"
    assert doc.root.get("height") == "100.000000mm"


def test_pdf_hint_overrides_detection():
    assert normalize(samples.GENERIC_PX, source_hint="pdf").source == "pdf"


def test_no_size_is_an_import_problem():
    with pytest.raises(ImportProblem, match="no page size"):
        normalize(samples.NO_SIZE)


def test_not_svg_is_an_import_problem():
    with pytest.raises(ImportProblem):
        normalize(b"hello")
    with pytest.raises(ImportProblem):
        normalize(b"<html></html>")


def test_detect_source_direct():
    doc = normalize(samples.INKSCAPE_MM)
    assert detect_source(doc.root, samples.INKSCAPE_MM) == "inkscape"
