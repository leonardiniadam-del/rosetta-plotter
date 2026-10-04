import math

import pytest

from rosetta.geometry import EDGE_TOLERANCE_MM, MIN_RUN_MM, clip_polyline, contains

RECT = (0.0, 0.0, 10.0, 10.0)
PAGE = (0.0, 0.0, 100.0, 100.0)
NOISY = 100.0000032  # what a "100 mm" edge looks like after EMS's 7-digit transform


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


def test_page_sized_border_with_float_noise_keeps_all_four_sides():
    border = [(0.0, 0.0), (NOISY, 0.0), (NOISY, NOISY), (0.0, NOISY), (0.0, 0.0)]
    runs = clip_polyline(border, PAGE)
    assert len(runs) == 1
    assert len(runs[0]) == 5
    assert max(x for x, _ in runs[0]) == 100.0  # clamped onto the edge


def test_edge_hugging_line_with_tiny_excursion_is_kept_whole():
    line = [(10, 1), (10, 3), (10.000000000000002, 5), (10, 7), (10, 9)]
    runs = clip_polyline(line, (0, 0, 10, 10))
    assert len(runs) == 1 and len(runs[0]) == 5


def test_circle_touching_all_edges_stays_one_run():
    circle = [
        (50 + 50.0000032 * math.cos(a), 50 + 50.0000032 * math.sin(a))
        for a in (2 * math.pi * i / 128 for i in range(129))
    ]
    runs = clip_polyline(circle, PAGE)
    assert len(runs) == 1 and len(runs[0]) == 129


def test_tangent_and_corner_touches_make_no_dots():
    assert clip_polyline([(-5, 5), (5, -5)], (0, 0, 10, 10)) == []  # touches corner (0, 0)
    assert clip_polyline([(10, 10), (15, 15)], (0, 0, 10, 10)) == []  # touches corner (10, 10)
    assert clip_polyline([(5, -5), (5, 0)], (0, 0, 10, 10)) == []  # touches the top edge


def test_runs_shorter_than_a_motor_step_are_dropped():
    assert clip_polyline([(1, 1), (1 + MIN_RUN_MM / 2, 1)], (0, 0, 10, 10)) == []


def test_fully_inside_float_points_are_returned_exactly():
    line = [(0.1, 0.2), (3.3, 4.4), (7.7, 1.1)]
    assert clip_polyline(line, (0, 0, 10, 10)) == [line]


def test_duplicate_points_are_removed():
    assert clip_polyline([(10, 1), (10, 3), (10, 3)], (0, 0, 10, 10)) == [[(10, 1), (10, 3)]]


def test_contains_uses_the_same_edge_tolerance():
    assert contains((0, 0, 10, 10), (10 + EDGE_TOLERANCE_MM / 2, 0))
    assert not contains((0, 0, 10, 10), (10 + EDGE_TOLERANCE_MM * 2, 0))
