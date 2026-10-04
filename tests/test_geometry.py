import pytest

from rosetta.geometry import bbox, contains, intersect, place_point, rotated_size

# A 40 x 20 mm artwork. Its top-right corner is (40, 0).
W, H = 40.0, 20.0


def test_rotated_size():
    assert rotated_size(W, H, 0) == (W, H)
    assert rotated_size(W, H, 90) == (H, W)
    assert rotated_size(W, H, 180) == (W, H)
    assert rotated_size(W, H, -90) == (H, W)


def test_rotation_must_be_multiple_of_90():
    with pytest.raises(ValueError):
        rotated_size(W, H, 45)


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
