import pytest

from rosetta.compose import (
    DEFAULT_MARGIN_MM, REACH_EDGE_INSET_MM, ColorGroup, Material, PlacedPiece, Placement,
    compose_job, initial_placement,
)
from rosetta.flatten import Shape
from rosetta.geometry import place_point
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
    assert ColorGroup("#000000").polylines is not ColorGroup("#000000").polylines


def test_rotated_pieces_land_exactly():
    # A 20 x 10 piece with a mark at its top-right corner (20, 0).
    art = _art(20, 10, [_line("#000000", (20, 0), (20, 5))])
    paper = Material(0, 0, 100, 100)
    at_90 = compose_job(A4_MACHINE, paper, [PlacedPiece(art, Placement(x=10, y=10, rotation=90))])
    # Clockwise 90: the rotated box is 10 x 20; top-right (20, 0) -> (10, 20), (20, 5) -> (5, 20).
    assert at_90.groups[0].polylines[0] == pytest.approx([(20, 30), (15, 30)])
    at_270 = compose_job(A4_MACHINE, paper, [PlacedPiece(art, Placement(x=10, y=10, rotation=270))])
    # 270: (20, 0) -> (0, 0), (20, 5) -> (5, 0).
    assert at_270.groups[0].polylines[0] == pytest.approx([(10, 10), (15, 10)])


def test_nothing_lands_on_the_far_y_edge_of_the_reach():
    art = _art(10, 400, [_line("#000000", (5, 0), (5, 400))])
    job = compose_job(A4_MACHINE, Material(0, 0, 300, 400), [PlacedPiece(art, Placement())])
    _, travel_y = A4_MACHINE.travel_mm
    far_y = max(y for line in job.groups[0].polylines for _, y in line)
    assert far_y == pytest.approx(travel_y - REACH_EDGE_INSET_MM)


def test_paper_entirely_outside_the_reach_draws_nothing():
    art = _art(10, 10, [_line("#000000", (0, 0), (10, 0))])
    job = compose_job(A4_MACHINE, Material(400, 0, 50, 50), [PlacedPiece(art, Placement())])
    assert job.groups == [] and job.ink_bbox is None and job.clipped is True


def test_a3_paper_on_the_a3_plotter_is_not_reported_as_clipped():
    a3_machine = get_model(2)  # reaches 296.926 mm in y; A3 paper is 297 mm
    art = _art(420, 297, [_line("#000000", (0, 297), (420, 297)), _line("#000000", (0, 0), (420, 0))])
    paper = Material(0, 0, 420, 297)
    job = compose_job(a3_machine, paper, [PlacedPiece(art, initial_placement(art, paper))])
    assert job.clipped is False


def test_portrait_art_respects_the_vertical_margin():
    placement = initial_placement(_art(100, 400, []), Material(0, 0, 200, 200))
    usable = 200 - 2 * DEFAULT_MARGIN_MM
    assert placement.scale == pytest.approx(usable / 400)
    assert placement.y == pytest.approx(DEFAULT_MARGIN_MM)


@pytest.mark.parametrize("rotation", [float("nan"), "90"])
def test_bad_rotations_are_rejected_even_for_empty_pieces(rotation):
    with pytest.raises(ValueError):
        compose_job(A4_MACHINE, Material(0, 0, 50, 50), [PlacedPiece(_art(10, 10, []), Placement(rotation=rotation))])


def test_a_turned_stretched_piece_lands_where_place_point_says():
    art = _art(40, 20, [_line("#000000", (0, 0), (40, 0), (40, 20))])
    placement = Placement(x=30, y=40, scale=2.0, rotation=33.5, scale_y=0.5)
    job = compose_job(A4_MACHINE, Material(0, 0, 200, 150), [PlacedPiece(art, placement)])
    expected = [place_point(p, 40, 20, 30, 40, 2.0, 33.5, (0, 0), 0.5) for p in [(0, 0), (40, 0), (40, 20)]]
    assert job.groups[0].polylines[0] == pytest.approx(expected)


def test_skipped_colors_are_left_out():
    art = _art(100, 100, [_line("#ff0000", (0, 0), (10, 0)), _line("#000000", (0, 5), (10, 5))])
    job = compose_job(A4_MACHINE, Material(0, 0, 200, 200), [PlacedPiece(art, Placement())],
                      skip_colors=frozenset({"#ff0000"}))
    assert [group.color for group in job.groups] == ["#000000"]


@pytest.mark.parametrize("scale_y", [0, -1, float("nan"), "half"])
def test_bad_stretches_are_rejected(scale_y):
    with pytest.raises(ValueError):
        compose_job(A4_MACHINE, Material(0, 0, 50, 50), [PlacedPiece(_art(10, 10, []), Placement(scale_y=scale_y))])


@pytest.mark.parametrize(
    "paper",
    [Material(0, 0, 0, 100), Material(0, 0, -5, 100), Material(0, 0, float("nan"), 100), Material(float("inf"), 0, 100, 100)],
)
def test_bad_paper_is_rejected(paper):
    with pytest.raises(ValueError):
        compose_job(A4_MACHINE, paper, [])


def test_placement_is_immutable():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        Placement().x = 5
