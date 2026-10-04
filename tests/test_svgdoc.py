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


OLD_ILLUSTRATOR_DOCTYPE = b"""<?xml version="1.0" encoding="utf-8"?>
<!-- Generator: Adobe Illustrator 16.0.0, SVG Export Plug-In . SVG Version: 6.00 Build 0)  -->
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" [
  <!ENTITY ns_svg "http://www.w3.org/2000/svg">
  <!ENTITY ns_xlink "http://www.w3.org/1999/xlink">
]>
<svg version="1.1" xmlns="&ns_svg;" xmlns:xlink="&ns_xlink;" width="612px" height="792px" viewBox="0 0 612 792">
  <line fill="none" stroke="#000000" x1="72" y1="72" x2="144" y2="72"/>
</svg>"""


def test_old_illustrator_doctype_entities_parse():
    doc = normalize(OLD_ILLUSTRATOR_DOCTYPE)
    assert doc.source == "illustrator"
    assert (doc.width_mm, doc.height_mm) == pytest.approx((215.9, 279.4))


def test_pdf_hint_reads_unitless_sizes_as_points():
    assert normalize(samples.GENERIC_PX, source_hint="pdf").width_mm == pytest.approx(96 * 25.4 / 72)


def test_viewbox_only_without_fingerprints_is_read_as_points():
    raw = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 566.929134 283.464567"><line x2="1" stroke="red"/></svg>'
    doc = normalize(raw)
    assert doc.source == "svg"
    assert (doc.width_mm, doc.height_mm) == pytest.approx((200.0, 100.0), abs=0.001)


def test_inkscape_file_mentioning_cls_1_stays_inkscape():
    raw = (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
           b'width="96" height="48"><text>.cls-1</text></svg>')
    doc = normalize(raw)
    assert doc.source == "inkscape"
    assert doc.width_mm == pytest.approx(25.4)


def test_one_dimension_takes_the_other_from_viewbox_aspect():
    raw = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" viewBox="0 0 200 100"/>'
    doc = normalize(raw)
    assert (doc.width_mm, doc.height_mm) == pytest.approx((100.0, 50.0))


@pytest.mark.parametrize(
    "raw",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 nan nan"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg" width="-5mm" height="5mm"/>',
    ],
)
def test_unusable_sizes_are_import_problems(raw):
    with pytest.raises(ImportProblem):
        normalize(raw)


def test_unknown_source_hint_is_a_programming_error():
    with pytest.raises(ValueError):
        normalize(samples.GENERIC_PX, source_hint="Illustrator")
