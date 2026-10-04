import pytest

from rosetta.compose import (
    DEFAULT_MARGIN_MM, REACH_EDGE_INSET_MM, ColorGroup, Material, PlacedPiece, Placement,
    compose_job, initial_placement,
)
from rosetta.flatten import Shape
from rosetta.loader import Artwork
from rosetta.models import get_model

A4_MACHINE = get_model(1)  # 299.974 x 217.932 mm


def _art(width, height, shapes):
    return Artwork("art", width, height, shapes, [], "svg")


def _line(color, *points, stroked=True):
    return Shape((tuple(points),), color, stroked, not stroked)


def test_groups_by_color_in_first_appearance_order():
    art = _art(100, 100, [
        _line("#ff0000", (0, 0), (10, 0)),
        _line("#000000", (0, 5), (10, 5)),
        _line("#ff0000", (0, 9), (10, 9)),
    ])
    job = compose_job(A4_MACHINE, Material(0, 0, 200, 200), [PlacedPiece(art, Placement())])
    assert [group.color for group in job.groups] == ["#ff0000", "#000000"]
    assert len(job.groups[0].polylines) == 2
    assert job.groups[0].name == "red"


def test_material_offset_and_placement_applied():
    art = _art(10, 10, [_line("#000000", (0, 0), (10, 0))])
    job = compose_job(A4_MACHINE, Material(20, 30, 100, 100),
                      [PlacedPiece(art, Placement(x=5, y=5, scale=2.0))])
    assert job.groups[0].polylines[0] == pytest.approx([(25, 35), (45, 35)])
    assert job.ink_bbox == pytest.approx((25, 35, 45, 35))
    assert job.clipped is False


def test_clipped_to_paper_and_flagged():
    art = _art(100, 10, [_line("#000000", (0, 0), (100, 0))])
    job = compose_job(A4_MACHINE, Material(0, 0, 50, 50), [PlacedPiece(art, Placement(x=0, y=1))])
    assert job.groups[0].polylines[0] == pytest.approx([(0, 1), (50, 1)])
    assert job.clipped is True


def test_clipped_to_machine_reach():
    art = _art(10, 10, [_line("#000000", (0, 0), (10, 0))])
    # Paper hangs past the A4 machine's 299.974 mm reach.
    job = compose_job(A4_MACHINE, Material(295, 0, 50, 50), [PlacedPiece(art, Placement(x=0, y=1))])
    assert job.groups[0].polylines[0][-1][0] == pytest.approx(299.974 - REACH_EDGE_INSET_MM)
    assert job.clipped is True


def test_nothing_lands_on_the_far_edge_of_the_reach():
    # EMS skips lines lying exactly on the page's far edges, so Rosetta stays just inside.
    art = _art(400, 10, [_line("#000000", (0, 5), (400, 5))])
    job = compose_job(A4_MACHINE, Material(0, 0, 400, 300), [PlacedPiece(art, Placement())])
    travel_x, _ = A4_MACHINE.travel_mm
    far_x = max(x for line in job.groups[0].polylines for x, _ in line)
    assert far_x == pytest.approx(travel_x - REACH_EDGE_INSET_MM)


@pytest.mark.parametrize(
    "placement",
    [Placement(scale=0), Placement(scale=-1), Placement(scale=float("nan")), Placement(x=float("inf"))],
)
def test_invalid_placements_are_rejected(placement):
    art = _art(10, 10, [_line("#000000", (0, 0), (10, 0))])
    with pytest.raises(ValueError):
        compose_job(A4_MACHINE, Material(0, 0, 50, 50), [PlacedPiece(art, placement)])


def test_white_skipped_by_default_but_can_be_kept():
    art = _art(10, 10, [_line("#ffffff", (0, 0), (10, 0))])
    pieces = [PlacedPiece(art, Placement())]
    assert compose_job(A4_MACHINE, Material(0, 0, 50, 50), pieces).groups == []
    assert len(compose_job(A4_MACHINE, Material(0, 0, 50, 50), pieces, skip_white=False).groups) == 1


def test_initial_placement_matching_paper_goes_to_corner_and_never_overhangs():
    placement = initial_placement(_art(215.9, 279.4, []), Material(0, 0, 216, 279))
    assert (placement.x, placement.y, placement.rotation) == (0.0, 0.0, 0)
    assert placement.scale == pytest.approx(279 / 279.4)  # shrunk by the 0.4 mm it overhung


def test_initial_placement_centers_and_shrinks_to_fit():
    art = _art(400, 100, [])
    paper = Material(0, 0, 200, 200)
    placement = initial_placement(art, paper)
    usable = 200 - 2 * DEFAULT_MARGIN_MM
    assert placement.scale == pytest.approx(usable / 400)
    assert placement.x == pytest.approx(DEFAULT_MARGIN_MM)
    assert placement.y == pytest.approx((200 - 100 * placement.scale) / 2)


def test_initial_placement_small_art_keeps_size_and_centers():
    placement = initial_placement(_art(50, 20, []), Material(0, 0, 200, 100))
    assert placement == Placement(75, 40, 1.0, 0)


def test_color_group_defaults():
    assert ColorGroup("#0000ff").polylines == []
