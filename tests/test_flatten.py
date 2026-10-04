import math

import pytest

from rosetta.flatten import Shape, flatten
from rosetta.svgdoc import normalize
from tests import samples
from tests.helpers import shapes_bbox

MM_SVG_OPEN = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
               'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
               'width="100mm" height="100mm" viewBox="0 0 100 100">')


def _svg(body: str) -> bytes:
    return (MM_SVG_OPEN + body + "</svg>").encode()


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


def test_paint_on_the_svg_root_is_inherited():
    raw = (b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100" '
           b'fill="none" stroke="red"><line x2="50"/><path d="M0 10 L50 10 L50 30"/></svg>')
    shapes = flatten(normalize(raw))
    assert [(s.color, s.stroked, s.filled) for s in shapes] == [("#ff0000", True, False)] * 2


def test_fill_only_open_path_is_closed():
    shape, = flatten(normalize(_svg('<path d="M10 10 L50 10 L50 40" fill="red"/>')))
    assert len(shape.polylines[0]) == 4
    assert shape.polylines[0][-1] == pytest.approx(shape.polylines[0][0])


def test_zero_length_paths_are_dropped():
    shapes = flatten(normalize(_svg('<path d="M5 5 L5 5" stroke="black"/><line x2="10" stroke="black"/>')))
    assert len(shapes) == 1


def test_plain_href_use_is_followed():
    body = '<defs><path id="p" d="M0 0 L10 0" stroke="black"/></defs><use href="#p" y="5"/>'
    shape, = flatten(normalize(_svg(body)))
    start, end = shape.polylines[0]
    assert start == pytest.approx((0, 5))
    assert end == pytest.approx((10, 5))


def test_percent_layers_are_skipped_like_ems():
    body = ('<g inkscape:groupmode="layer" inkscape:label="%notes"><line x2="50" stroke="black"/></g>'
            '<g inkscape:groupmode="layer" inkscape:label="1"><line y1="5" x2="50" y2="5" stroke="black"/></g>')
    assert len(flatten(normalize(_svg(body)))) == 1


def test_malformed_transform_becomes_import_problem():
    from rosetta.errors import ImportProblem

    with pytest.raises(ImportProblem, match="couldn't be read"):
        flatten(normalize(_svg('<rect width="10" height="10" transform="rotate(" stroke="black"/>')))


PARITY_CASES = {
    "nested_transforms": '<g transform="translate(10,10) rotate(30)"><g transform="scale(2)">'
                         '<path d="M0 0 L20 0 L20 10" stroke="black" fill="none"/></g></g>',
    "use_symbol": '<defs><symbol id="s"><rect width="10" height="5" stroke="black" fill="none"/></symbol></defs>'
                  '<use xlink:href="#s" x="20" y="20"/>',
    "arcs_and_curves": '<path d="M10 50 A20 20 0 0 1 50 50 C60 30 80 30 90 50 Q95 70 99 50" stroke="black" fill="none"/>',
    "rounded_rect": '<rect x="10" y="10" width="40" height="20" rx="5" stroke="black" fill="none"/>',
    "polygon_and_circle": '<polygon points="10,10 40,10 25,35" stroke="black" fill="none"/>'
                          '<circle cx="70" cy="30" r="15" stroke="black" fill="none"/>',
    "hidden_group": '<g display="none"><line x2="90" stroke="black"/></g>'
                    '<line x1="5" y1="90" x2="95" y2="90" stroke="black"/>',
}


def _ems_pendown_mm(svg: str) -> float:
    from pyaxidraw import axidraw

    ad = axidraw.AxiDraw()
    ad.plot_setup(svg)
    ad.options.preview = True
    ad.options.rendering = 0
    ad.options.reordering = 4  # strict order, no path joining
    ad.plot_run()
    stats = ad.plot_status.stats
    return max(stats.down_travel_tot, stats.down_travel_inch) * 25.4


def _length_mm(shapes) -> float:
    return sum(
        math.dist(a, b) for shape in shapes for line in shape.polylines for a, b in zip(line, line[1:])
    )


@pytest.mark.parametrize("name", sorted(PARITY_CASES))
def test_matches_what_ems_would_draw(name):
    svg = MM_SVG_OPEN + PARITY_CASES[name] + "</svg>"
    assert _length_mm(flatten(normalize(svg.encode()))) == pytest.approx(_ems_pendown_mm(svg), abs=0.05)
