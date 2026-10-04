import pytest

from rosetta.geometry import clip_polyline

RECT = (0.0, 0.0, 10.0, 10.0)


def test_fully_inside_unchanged():
    line = [(1, 1), (5, 5), (9, 1)]
    assert clip_polyline(line, RECT) == [line]


def test_fully_outside_removed():
    assert clip_polyline([(11, 11), (20, 20)], RECT) == []


def test_crossing_out_and_back_in_splits_in_two():
    parts = clip_polyline([(5, 5), (15, 5), (15, 8), (5, 8)], RECT)
    assert len(parts) == 2
    assert parts[0] == pytest.approx([(5, 5), (10, 5)])
    assert parts[1] == pytest.approx([(10, 8), (5, 8)])


def test_segment_passing_through_is_trimmed_both_ends():
    parts = clip_polyline([(-5, 5), (15, 5)], RECT)
    assert parts == [pytest.approx([(0, 5), (10, 5)])]


def test_degenerate_input():
    assert clip_polyline([(1, 1)], RECT) == []
    assert clip_polyline([], RECT) == []
