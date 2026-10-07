import math
from itertools import pairwise

import pytest

from rosetta.compose import ColorGroup
from rosetta.engine.options import PlotSettings
from rosetta.engine.preview import plan_layer
from rosetta.engine.runner import estimate
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg

SETTINGS = PlotSettings(model=1)
SQUARE = [(10.0, 10.0), (110.0, 10.0), (110.0, 110.0), (10.0, 110.0), (10.0, 10.0)]
LINE = [(20.0, 150.0), (120.0, 150.0)]


def _plot(*lines) -> str:
    return plot_svg(get_model(1), [ColorGroup("#000000", list(lines))])


def _length(points) -> float:
    return sum(math.dist(a[:2], b[:2]) for a, b in pairwise(points))


def test_the_plan_agrees_with_the_estimate():
    svg = _plot(SQUARE, LINE)
    plan, expected = plan_layer(svg, 1, SETTINGS), estimate(svg, 1, SETTINGS)
    assert plan.seconds == pytest.approx(expected.seconds)
    assert plan.pendown_m == pytest.approx(expected.pendown_m)


def test_the_plan_draws_every_line_once():
    plan = plan_layer(_plot(SQUARE, LINE), 1, SETTINGS)
    assert sum(_length(run.points) for run in plan.runs if run.down) == pytest.approx(500.0, abs=0.5)


def test_the_plan_starts_and_ends_at_home():
    runs = plan_layer(_plot(SQUARE), 1, SETTINGS).runs
    assert not runs[0].down and runs[0].points[0][:2] == pytest.approx((0, 0), abs=0.01)
    assert not runs[-1].down and runs[-1].points[-1][:2] == pytest.approx((0, 0), abs=0.01)


def test_times_rise_to_the_estimate():
    plan = plan_layer(_plot(SQUARE, LINE), 1, SETTINGS)
    times = [t for run in plan.runs for _x, _y, t in run.points]
    assert times == sorted(times)
    assert times[-1] == pytest.approx(plan.seconds)


def test_pen_up_and_pen_down_runs_take_turns():
    runs = plan_layer(_plot(SQUARE, LINE), 1, SETTINGS).runs
    assert all(a.down != b.down for a, b in pairwise(runs))


def test_straight_moves_keep_only_their_corners():
    drawing = [run for run in plan_layer(_plot(SQUARE), 1, SETTINGS).runs if run.down]
    assert len(drawing) == 1 and len(drawing[0].points) == 5


def test_an_unreadable_plot_is_a_value_error():
    with pytest.raises(ValueError):
        plan_layer("<svg", 1, SETTINGS)
