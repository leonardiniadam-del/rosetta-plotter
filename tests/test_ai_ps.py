"""Rhino's old-style (PostScript) Illustrator export opens like any other drawing."""
import pytest

from rosetta.ai_ps import ai_ps_to_svg, is_postscript_ai
from rosetta.app.session import pages_in
from rosetta.errors import ImportProblem
from rosetta.loader import load_artwork

HEAD = """%!PS-Adobe-3.0
%%Creator: Rhinoceros
%%BoundingBox: 0 0 144 72
%%EndComments
%%BeginSetup
Adobe_cmykcolor /initialize get exec
%%EndSetup
"""
LAYER = """%AI5_BeginLayer
{visible} 1 1 1 0 0 -1 150 150 150 Lb
(Layer::Sub) Ln
0 A
1 0 0 XA
0 0 1 Xa
0 i 1 J 1 j 0.5 w 4 M []0 d
{body}
LB
%AI5_EndLayer--
"""
LINE = "0 72 m\n72 0 L\nS\n"
TAIL = "%%Trailer\n%%EOF\n"


def write(tmp_path, *layers, name="rhino.ai"):
    path = tmp_path / name
    path.write_bytes((HEAD + "".join(layers) + TAIL).encode("latin-1"))
    return path


def test_a_stroked_line_is_read_in_page_coordinates(tmp_path):
    path = write(tmp_path, LAYER.format(visible=1, body=LINE))
    assert is_postscript_ai(path)
    page = ai_ps_to_svg(path)
    assert 'width="144.0000pt"' in page.svg and 'height="72.0000pt"' in page.svg
    assert 'd="M0.0000 0.0000 L72.0000 72.0000"' in page.svg  # y is flipped: PostScript's y runs up
    assert 'stroke="#ff0000"' in page.svg and 'fill="none"' in page.svg
    assert not page.has_text


def test_it_loads_as_artwork_with_one_page(tmp_path):
    path = write(tmp_path, LAYER.format(visible=1, body=LINE))
    art = load_artwork(path)
    assert pages_in(path) == 1
    assert art.width_mm == pytest.approx(50.8) and art.height_mm == pytest.approx(25.4)
    assert len(art.shapes) == 1
    (line,) = art.shapes[0].polylines
    assert line[0] == pytest.approx((0, 0)) and line[-1] == pytest.approx((25.4, 25.4))


def test_curves_and_closed_paths(tmp_path):
    body = "0 0 m\n0 36 36 72 72 72 c\n72 0 L\ns\n"
    page = ai_ps_to_svg(write(tmp_path, LAYER.format(visible=1, body=body)))
    assert "C0.0000 36.0000 36.0000 0.0000 72.0000 0.0000" in page.svg
    assert page.svg.count(" Z") == 1


def test_hidden_layers_are_left_out(tmp_path):
    path = write(tmp_path, LAYER.format(visible=0, body=LINE), LAYER.format(visible=1, body="0 0 m\n144 0 L\nS\n"))
    assert ai_ps_to_svg(path).svg.count("<path") == 1


def test_text_is_skipped_and_reported(tmp_path):
    text = "0 To\n1 0 0 1 10 10 0 Tp\nTP\n0 Tr\n/_ArialMT 12 Tf\n(DN \\(up\\)) Tx\nTO\n"
    path = write(tmp_path, LAYER.format(visible=1, body=text + LINE))
    page = ai_ps_to_svg(path)
    assert page.has_text and page.svg.count("<path") == 1
    assert "pdf_text" in [issue.code for issue in load_artwork(path).issues]


def test_a_file_without_a_size_says_so(tmp_path):
    path = tmp_path / "bare.ai"
    path.write_bytes(b"%!PS-Adobe-3.0\n%%EndSetup\n0 0 m\n1 1 L\nS\n")
    with pytest.raises(ImportProblem, match="how big"):
        load_artwork(path)
