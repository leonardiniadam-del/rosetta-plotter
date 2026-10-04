import pytest

from rosetta.flatten import Shape, flatten
from rosetta.geometry_testing import shapes_bbox
from rosetta.svgdoc import normalize
from tests import samples


def _by_color(shapes):
    result = {}
    for shape in shapes:
        result.setdefault(shape.color, []).append(shape)
    return result


def test_illustrator_square_and_circle_in_mm():
    shapes = flatten(normalize(samples.ILLUSTRATOR_EXPORT))
    groups = _by_color(shapes)
    assert set(groups) == {"#ff0000", "#0000ff"}
    assert shapes_bbox(groups["#ff0000"]) == pytest.approx((0, 0, 100, 100), abs=0.01)
    assert shapes_bbox(groups["#0000ff"]) == pytest.approx((125, 25, 175, 75), abs=0.05)


def test_stroked_and_filled_flags():
    groups = _by_color(flatten(normalize(samples.ILLUSTRATOR_EXPORT)))
    square, = groups["#ff0000"]
    circle, = groups["#0000ff"]
    assert (square.stroked, square.filled) == (True, False)
    assert (circle.stroked, circle.filled) == (False, True)


def test_affinity_line_in_mm():
    shapes = flatten(normalize(samples.AFFINITY_EXPORT))
    assert len(shapes) == 1
    assert shapes[0].color == "#0000ff"
    assert shapes[0].polylines[0][0] == pytest.approx((10.0, 10.0), abs=0.001)
    assert shapes[0].polylines[0][-1] == pytest.approx((100.0, 10.0), abs=0.001)


def test_illustrator_px_line_is_points():
    shape, = flatten(normalize(samples.ILLUSTRATOR_PX))
    assert shape.polylines[0][0] == pytest.approx((25.4, 25.4), abs=0.001)
    assert shape.polylines[0][-1] == pytest.approx((50.8, 25.4), abs=0.001)


def test_generic_unitless_line():
    shape, = flatten(normalize(samples.GENERIC_PX))
    assert shape.polylines[0][-1] == pytest.approx((25.4, 12.7), abs=0.001)


def test_invisible_shapes_dropped_and_default_fill_is_black():
    raw = b"""<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">
      <rect width="5" height="5" fill="none"/>
      <rect x="5" y="5" width="5" height="5"/>
      <line x1="0" y1="0" x2="10" y2="10"/>
    </svg>"""
    shapes = flatten(normalize(raw))
    # The fill="none" rect has no stroke: invisible. The bare rect is black-filled.
    # The bare line has no stroke and lines can't be filled: invisible.
    assert len(shapes) == 1
    assert isinstance(shapes[0], Shape)
    assert shapes[0].color == "#000000"
    assert (shapes[0].stroked, shapes[0].filled) == (False, True)


def test_parser_failure_becomes_import_problem(monkeypatch):
    from axidrawinternal import digest_svg

    from rosetta.errors import ImportProblem

    def broken(*args, **kwargs):
        raise ValueError("unexpected input")

    monkeypatch.setattr(digest_svg.DigestSVG, "process_svg", broken)
    with pytest.raises(ImportProblem, match="couldn't be read"):
        flatten(normalize(samples.GENERIC_PX))
