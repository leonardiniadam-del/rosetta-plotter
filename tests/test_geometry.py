import math

import pytest

from rosetta.geometry import bbox, contains, intersect, place_point, rotated_size

# A 40 x 20 mm artwork. Its top-right corner is (40, 0).
W, H = 40.0, 20.0


def test_rotated_size():
    assert rotated_size(W, H, 0) == (W, H)
    assert rotated_size(W, H, 90) == (H, W)
    assert rotated_size(W, H, 180) == (W, H)
    assert rotated_size(W, H, -90) == (H, W)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "90"])
def test_rotation_must_be_a_finite_number(bad):
    with pytest.raises((ValueError, TypeError)):
        rotated_size(W, H, bad)


def test_rotation_wraps_around():
    assert rotated_size(W, H, 450) == rotated_size(W, H, 90)
    assert rotated_size(W, H, -90) == rotated_size(W, H, 270)


def test_rotated_size_at_a_free_angle():
    assert rotated_size(10, 10, 45) == pytest.approx((10 * math.sqrt(2), 10 * math.sqrt(2)))


def test_a_free_angle_keeps_the_art_in_its_upright_box():
    width, height = rotated_size(40, 20, 30)
    corners = [place_point(c, 40, 20, 0, 0, 1.0, 30, (0, 0)) for c in ((0, 0), (40, 0), (40, 20), (0, 20))]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    assert (min(xs), min(ys)) == pytest.approx((0, 0), abs=1e-9)
    assert (max(xs), max(ys)) == pytest.approx((width, height))


def test_turning_is_clockwise_on_screen():
    right_end = place_point((40, 0), 40, 20, 0, 0, 1.0, 10, (0, 0))
    left_end = place_point((0, 0), 40, 20, 0, 0, 1.0, 10, (0, 0))
    assert right_end[1] > left_end[1]  # the far end of the top edge moves toward the student


def test_quarter_turns_agree_with_nearby_free_angles():
    for turn in (90, 180, 270):
        exact = place_point((13.5, 7.25), 40, 20, 3, 4, 1.5, turn, (2, 1))
        near = place_point((13.5, 7.25), 40, 20, 3, 4, 1.5, turn - 1e-7, (2, 1))
        assert near == pytest.approx(exact, abs=1e-4)


def test_stretching_scales_each_side_of_the_artwork():
    assert place_point((40, 20), 40, 20, 0, 0, 2.0, 0, (0, 0), scale_y=0.5) == pytest.approx((80, 10))
    assert place_point((40, 20), 40, 20, 0, 0, 2.0, 90, (0, 0), scale_y=0.5) == pytest.approx((0, 80))
    assert rotated_size(40 * 2.0, 20 * 0.5, 90) == (10.0, 80.0)


@pytest.mark.parametrize(
    "rotation, expected",
    [
        (0, (40.0, 0.0)),    # top-right stays top-right
        (90, (20.0, 40.0)),  # clockwise: top-right -> bottom-right
        (180, (0.0, 20.0)),  # -> bottom-left
        (270, (0.0, 0.0)),   # -> top-left
    ],
)
def test_place_point_rotations_keep_art_in_its_box(rotation, expected):
    assert place_point((40.0, 0.0), W, H, 0, 0, 1.0, rotation, (0, 0)) == pytest.approx(expected)


def test_place_point_scale_offset_and_material_origin():
    # scale 2, placed at (5, 7) on paper whose corner is at (100, 50) on the bed
    assert place_point((10.0, 10.0), W, H, 5, 7, 2.0, 0, (100, 50)) == pytest.approx((125.0, 77.0))


def test_bbox_and_contains():
    assert bbox([[(1, 2), (5, 3)], [(0, 9)]]) == (0, 2, 5, 9)
    assert bbox([]) is None
    assert contains((0, 0, 10, 10), (10, 0))
    assert not contains((0, 0, 10, 10), (10.1, 0))


def test_intersect():
    assert intersect((0, 0, 10, 10), (5, 5, 20, 20)) == (5, 5, 10, 10)
    assert intersect((0, 0, 10, 10), (11, 11, 20, 20)) is None
