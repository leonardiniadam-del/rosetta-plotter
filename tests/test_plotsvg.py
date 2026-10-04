import pytest
from lxml import etree

from rosetta.compose import ColorGroup
from rosetta.flatten import flatten
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg
from rosetta.svgdoc import INKSCAPE_NS, normalize

GROUPS = [
    ColorGroup("#ff0000", [[(10.0, 10.0), (110.0, 10.0)]]),
    ColorGroup("#000000", [[(20.0, 20.0), (20.0, 120.0), (60.0, 120.0)]]),
]


def test_page_is_machine_travel_in_mm():
    root = etree.fromstring(plot_svg(get_model(5), GROUPS).encode())
    assert root.get("width") == "864.1080mm"
    assert root.get("height") == "594.1060mm"
    assert root.get("viewBox") == "0 0 864.1080 594.1060"


def test_one_numbered_layer_per_color():
    root = etree.fromstring(plot_svg(get_model(1), GROUPS).encode())
    labels = [g.get(f"{{{INKSCAPE_NS}}}label") for g in root]
    modes = {g.get(f"{{{INKSCAPE_NS}}}groupmode") for g in root}
    assert labels == ["1", "2"]
    assert modes == {"layer"}


def test_no_xml_declaration():
    assert not plot_svg(get_model(1), GROUPS).startswith("<?xml")


def test_round_trip_through_ems_parser():
    shapes = flatten(normalize(plot_svg(get_model(1), GROUPS).encode()))
    assert [shape.color for shape in shapes] == ["#ff0000", "#000000"]
    expected = [(20, 20), (20, 120), (60, 120)]
    assert len(shapes[1].polylines[0]) == len(expected)
    for actual, point in zip(shapes[1].polylines[0], expected):
        assert actual == pytest.approx(point, abs=0.001)
