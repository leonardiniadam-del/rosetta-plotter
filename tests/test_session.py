import base64

import pymupdf
import pytest

from rosetta.app.payloads import job_payload, material_payload, piece_payload
from rosetta.app.session import DUPLICATE_OFFSET_MM, GONE, Session, pages_in
from rosetta.compose import Material
from rosetta.errors import ImportProblem, UserProblem
from rosetta.models import get_model

LETTER = Material(0.0, 0.0, 279.4, 215.9)
TWO_COLORS = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 100 50">
<path d="M10 10 H90" stroke="#000000" fill="none"/>
<path d="M10 30 H90.004" stroke="#ff0000" fill="none"/>
<rect x="0" y="0" width="100" height="50" fill="#ffffff"/>
</svg>"""


def _svg(tmp_path, text=TWO_COLORS, name="art.svg"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_an_import_lands_centered_on_the_paper(tmp_path):
    session = Session(LETTER)
    piece, shrunk = session.add(_svg(tmp_path))
    assert piece.id == "piece-1" and not shrunk
    assert (piece.placement.x, piece.placement.y) == pytest.approx(((279.4 - 100) / 2, (215.9 - 50) / 2))


def test_artwork_bigger_than_the_paper_is_shrunk_and_says_so(tmp_path):
    big = TWO_COLORS.replace('width="100mm" height="50mm"', 'width="1000mm" height="500mm"')
    piece, shrunk = Session(LETTER).add(_svg(tmp_path, big))
    assert shrunk and piece.placement.scale < 0.3


def test_place_duplicate_and_remove(tmp_path):
    session = Session(LETTER)
    first, _ = session.add(_svg(tmp_path))
    session.place(first.id, 5, 6, 0.5, 450)
    assert (first.placement.x, first.placement.y, first.placement.scale, first.placement.rotation) == (5, 6, 0.5, 90)
    copy = session.duplicate(first.id)
    assert copy.id == "piece-2" and copy.artwork is first.artwork
    assert (copy.placement.x, copy.placement.y) == (5 + DUPLICATE_OFFSET_MM, 6 + DUPLICATE_OFFSET_MM)
    session.remove(first.id)
    assert [piece.id for piece in session.pieces] == ["piece-2"]
    with pytest.raises(UserProblem, match=GONE):
        session.get(first.id)


@pytest.mark.parametrize("x, y, scale, rotation", [
    (float("nan"), 0, 1, 0), (0, float("inf"), 1, 0), (0, 0, 0, 0), (0, 0, -1, 0), (0, 0, 1, 45),
])
def test_bad_placements_are_refused(tmp_path, x, y, scale, rotation):
    session = Session(LETTER)
    piece, _ = session.add(_svg(tmp_path))
    with pytest.raises(ValueError):
        session.place(piece.id, x, y, scale, rotation)


def test_compose_skips_white_unless_asked(tmp_path):
    session = Session(LETTER)
    session.add(_svg(tmp_path))
    assert [group.name for group in session.compose(get_model(1)).groups] == ["black", "red"]
    session.skip_white = False
    assert [group.name for group in session.compose(get_model(1)).groups] == ["black", "red", "white"]


def test_page_counts(tmp_path):
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page()
    doc.save(tmp_path / "three.pdf")
    doc.close()
    assert pages_in(tmp_path / "three.pdf") == 3
    assert pages_in(_svg(tmp_path)) == 1
    with pytest.raises(ImportProblem, match="can't be found"):
        pages_in(tmp_path / "missing.pdf")


def test_piece_payload_groups_lines_by_color(tmp_path):
    piece, _ = Session(LETTER).add(_svg(tmp_path))
    payload = piece_payload(piece)
    assert payload["id"] == "piece-1" and payload["name"] == "art"
    assert (payload["width_mm"], payload["height_mm"]) == pytest.approx((100, 50))
    groups = {group["color"]: group for group in payload["groups"]}
    assert groups["#000000"]["lines"] == [[10.0, 10.0, 90.0, 10.0]]
    assert groups["#ff0000"]["lines"] == [[10.0, 30.0, 90.0, 30.0]]  # rounded to 0.01 mm
    assert groups["#ffffff"]["white"] and not groups["#000000"]["white"]
    assert {issue["code"] for issue in payload["issues"]} == {"white"}
    preview = payload["preview"].removeprefix("data:image/svg+xml;base64,")
    assert base64.b64decode(preview).decode("utf-8").startswith("<svg")


def test_material_payload_says_whether_the_paper_fits():
    assert material_payload(LETTER, get_model(1))["fits"] is True  # 279.4 x 215.9 on a 300 x 218 plotter
    a3 = material_payload(Material(0, 0, 420, 297), get_model(1))
    assert a3["fits"] is False and a3["reach"] == pytest.approx([299.97, 217.93], abs=0.01)
    assert material_payload(LETTER, None)["reach"] is None


def test_job_payload_lists_the_pens(tmp_path):
    session = Session(LETTER)
    session.add(_svg(tmp_path))
    payload = job_payload(session.compose(get_model(1)))
    assert [(c["layer"], c["name"], c["lines"]) for c in payload["colors"]] == [(1, "black", 1), (2, "red", 1)]
    assert not payload["empty"] and not payload["clipped"]
