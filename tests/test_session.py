import base64

import pymupdf
import pytest

from rosetta.app.payloads import colors_payload, job_payload, material_payload, piece_payload
from rosetta.app.session import DUPLICATE_OFFSET_MM, GONE, JOB_GONE, Session, pages_in
from rosetta.compose import Material
from rosetta.errors import ImportProblem, UserProblem
from rosetta.models import get_model

LETTER = Material(0.0, 0.0, 279.4, 215.9)
BIG = get_model(5)  # SE/A1: nothing on a Letter sheet is out of reach
TWO_COLORS = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 100 50">
<path d="M10 10 H90" stroke="#000000" fill="none"/>
<path d="M10 30 H90.004 V45" stroke="#ff0000" fill="none"/>
<rect x="0" y="0" width="100" height="50" fill="#ffffff"/>
</svg>"""


def _svg(tmp_path, text=TWO_COLORS, name="art.svg"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _session_with_job(tmp_path):
    session = Session(LETTER)
    job = session.load_job(_svg(tmp_path))
    return session, job


def test_importing_adds_a_job_without_placing_it(tmp_path):
    session, job = _session_with_job(tmp_path)
    assert job.id == "job-1" and job.artwork.name == "art"
    assert session.jobs == [job] and session.pieces == []


def test_a_job_is_placed_at_full_size_where_asked(tmp_path):
    big = TWO_COLORS.replace('width="100mm" height="50mm"', 'width="1000mm" height="500mm"')
    session = Session(LETTER)
    job = session.load_job(_svg(tmp_path, big))
    piece = session.place_job(job.id, 6.35, 6.35)
    assert (piece.id, piece.job_id) == ("piece-1", "job-1")
    p = piece.placement
    assert (p.x, p.y, p.scale, p.rotation, p.scale_y) == (6.35, 6.35, 1.0, 0.0, None)  # never shrunk


def test_a_job_can_be_placed_several_times_and_removed_with_its_copies(tmp_path):
    session, job = _session_with_job(tmp_path)
    first = session.place_job(job.id, 0, 0)
    second = session.place_job(job.id, 120, 0)
    assert session.remove_job(job.id) == [first.id, second.id]
    assert session.jobs == [] and session.pieces == []
    with pytest.raises(UserProblem, match=JOB_GONE):
        session.place_job(job.id, 0, 0)


def test_place_takes_any_angle_and_a_stretch(tmp_path):
    session, job = _session_with_job(tmp_path)
    piece = session.place_job(job.id, 0, 0)
    session.place(piece.id, 5, 6, 0.5, -30, 2.0)
    p = piece.placement
    assert (p.x, p.y, p.scale, p.rotation, p.scale_y) == (5, 6, 0.5, 330.0, 2.0)


@pytest.mark.parametrize("x, y, scale, rotation, scale_y", [
    (float("nan"), 0, 1, 0, None), (0, float("inf"), 1, 0, None), (0, 0, 0, 0, None),
    (0, 0, -1, 0, None), (0, 0, 1, float("nan"), None), (0, 0, 1, 0, 0), (0, 0, 1, 0, 1000),
])
def test_bad_placements_are_refused(tmp_path, x, y, scale, rotation, scale_y):
    session, job = _session_with_job(tmp_path)
    piece = session.place_job(job.id, 0, 0)
    with pytest.raises(ValueError):
        session.place(piece.id, x, y, scale, rotation, scale_y)


def test_duplicate_and_remove_pieces(tmp_path):
    session, job = _session_with_job(tmp_path)
    first = session.place_job(job.id, 5, 6)
    copy = session.duplicate(first.id)
    assert copy.id == "piece-2" and copy.job_id == job.id and copy.artwork is first.artwork
    assert (copy.placement.x, copy.placement.y) == (5 + DUPLICATE_OFFSET_MM, 6 + DUPLICATE_OFFSET_MM)
    session.remove(first.id)
    assert [piece.id for piece in session.pieces] == ["piece-2"]
    with pytest.raises(UserProblem, match=GONE):
        session.get(first.id)


def test_compose_skips_white_unless_asked(tmp_path):
    session, job = _session_with_job(tmp_path)
    session.place_job(job.id, 10, 10)
    assert [group.name for group in session.compose(get_model(1)).groups] == ["black", "red"]
    session.skip_white = False
    assert [group.name for group in session.compose(get_model(1)).groups] == ["black", "red", "white"]


def test_hidden_colors_are_left_out_unless_asked_for(tmp_path):
    session, job = _session_with_job(tmp_path)
    session.place_job(job.id, 10, 10)
    session.set_color_visible("#FF0000", False)
    assert [group.name for group in session.compose(BIG).groups] == ["black"]
    assert [group.name for group in session.compose(BIG, include_hidden=True).groups] == ["black", "red"]
    session.set_color_visible("#ff0000", True)
    assert [group.name for group in session.compose(BIG).groups] == ["black", "red"]


def test_rotate_paper_turns_the_paper_and_everything_on_it(tmp_path):
    session, job = _session_with_job(tmp_path)
    upright = session.place_job(job.id, 10, 20)
    turned = session.place_job(job.id, 120, 60)
    session.place(turned.id, 120, 60, 1.5, 33.5, 0.75)
    before = session.compose(BIG, include_hidden=True)
    session.rotate_paper()
    assert (session.material.width, session.material.height) == (215.9, 279.4)
    assert upright.placement.rotation == 90.0 and turned.placement.rotation == pytest.approx(123.5)
    after = session.compose(BIG, include_hidden=True)
    assert [group.color for group in after.groups] == [group.color for group in before.groups]
    for old, new in zip(before.groups, after.groups):
        assert len(new.polylines) == len(old.polylines)
        for old_line, new_line in zip(old.polylines, new.polylines):
            assert len(new_line) == len(old_line)
            for (px, py), moved in zip(old_line, new_line):
                # A point (px, py) on the old sheet is at (H - py, px) on the turned one (H = old height).
                assert moved == pytest.approx((215.9 - py, px), abs=1e-6)  # approx needs one point at a time


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


def test_job_payload_groups_lines_by_color(tmp_path):
    _session, job = _session_with_job(tmp_path)
    payload = job_payload(job)
    assert payload["id"] == "job-1" and payload["name"] == "art" and payload["page"] == 0
    assert (payload["width_mm"], payload["height_mm"]) == pytest.approx((100, 50))
    groups = {group["color"]: group for group in payload["groups"]}
    assert groups["#000000"]["lines"] == [[10.0, 10.0, 90.0, 10.0]]
    assert groups["#ff0000"]["lines"] == [[10.0, 30.0, 90.0, 30.0, 90.0, 45.0]]  # rounded to 0.01 mm
    assert groups["#ffffff"]["white"] and not groups["#000000"]["white"]
    assert {issue["code"] for issue in payload["issues"]} == {"white"}
    preview = payload["preview"].removeprefix("data:image/svg+xml;base64,")
    assert base64.b64decode(preview).decode("utf-8").startswith("<svg")


def test_piece_payload_is_slim_and_always_has_both_scales(tmp_path):
    session, job = _session_with_job(tmp_path)
    piece = session.place_job(job.id, 1, 2)
    assert piece_payload(piece) == {
        "id": "piece-1", "job_id": "job-1",
        "placement": {"x": 1.0, "y": 2.0, "scale": 1.0, "scale_y": 1.0, "rotation": 0.0},
    }


def test_colors_payload_numbers_only_the_visible_pens(tmp_path):
    session, job = _session_with_job(tmp_path)
    session.place_job(job.id, 10, 10)
    session.set_color_visible("#000000", False)
    payload = colors_payload(session.compose(BIG, include_hidden=True), session.hidden_colors)
    assert [(c["layer"], c["name"], c["visible"]) for c in payload["colors"]] == [(None, "black", False), (1, "red", True)]
    assert not payload["empty"] and not payload["clipped"]


def test_material_payload_says_whether_the_paper_fits():
    assert material_payload(LETTER, get_model(1))["fits"] is True  # 279.4 x 215.9 on a 300 x 218 plotter
    a3 = material_payload(Material(0, 0, 420, 297), get_model(1))
    assert a3["fits"] is False and a3["reach"] == pytest.approx([299.97, 217.93], abs=0.01)
    assert material_payload(LETTER, None)["reach"] is None
