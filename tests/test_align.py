"""At a pen change, the new pen is lined up with lines already drawn, and its layer plots that far over."""
import pytest

from rosetta.app.plotjob import NOT_NOW, NUDGE_TOO_FAR
from rosetta.compose import ColorGroup
from rosetta.engine.options import PlotSettings
from rosetta.engine.preview import plan_layer
from rosetta.errors import UserProblem
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg, shift_layer
from tests.fake_ebb import skip_engine_waits
from tests.test_plotjob import TWO_COLORS, Rig

SQUARE = [(10.0, 10.0), (110.0, 10.0), (110.0, 110.0), (10.0, 110.0), (10.0, 10.0)]
LINE = [(20.0, 150.0), (120.0, 150.0)]


@pytest.fixture(autouse=True)
def fast_engine(monkeypatch):
    skip_engine_waits(monkeypatch)


def _down_points(svg: str, layer: int):
    plan = plan_layer(svg, layer, PlotSettings(model=1))
    return [point[:2] for run in plan.runs if run.down for point in run.points]


def test_the_engine_plots_a_shifted_layer_that_far_over_and_leaves_the_others():
    svg = plot_svg(get_model(1), [ColorGroup("#000000", [SQUARE]), ColorGroup("#ff0000", [LINE])])
    shifted = shift_layer(svg, 2, 0.4, -0.3)
    before, after = _down_points(svg, 2), _down_points(shifted, 2)
    assert len(before) == len(after) > 1
    for (x0, y0), (x1, y1) in zip(before, after):
        assert (x1 - x0, y1 - y0) == pytest.approx((0.4, -0.3), abs=0.02)
    assert _down_points(shifted, 1) == pytest.approx(_down_points(svg, 1))


def test_shifting_a_layer_that_is_not_there_fails():
    svg = plot_svg(get_model(1), [ColorGroup("#000000", [SQUARE])])
    with pytest.raises(ValueError):
        shift_layer(svg, 2, 1, 1)


def _at_second_pen(tmp_path) -> Rig:
    rig = Rig(tmp_path, TWO_COLORS)
    rig.controller.prepare()
    rig.controller.start()
    rig.controller.continue_pen()  # the black pen
    rig.wait_until("load_pen")
    return rig


def test_the_arrows_nudge_from_home_and_the_nudges_add_up(tmp_path):
    rig = _at_second_pen(tmp_path)
    assert rig.controller.status()["align"] == {"available": True, "target": None, "offset": [0.0, 0.0]}
    rig.controller.align_jog(0.5, 0)
    rig.controller.align_jog(0, 0.1)
    assert rig.controller.status()["align"]["offset"] == pytest.approx([0.5, 0.1], abs=0.02)
    assert rig.machine.status()["position"] == pytest.approx([0.5, 0.1], abs=0.05)


def test_travel_is_not_a_nudge_and_nudges_count_from_there(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_jog(0.5, 0)
    rig.controller.align_move(30, 30)  # the Move pen tool: to a line the black pen drew
    status = rig.controller.status()["align"]
    assert status["target"] == pytest.approx([30, 30], abs=0.05) and status["offset"] == [0.0, 0.0]

    rig.controller.align_pen(True)
    rig.controller.align_jog(0.3, 0)
    rig.controller.align_jog(0, -0.2)
    assert rig.controller.status()["align"]["offset"] == pytest.approx([0.3, -0.2], abs=0.02)
    assert rig.machine.status()["position"] == pytest.approx([30.3, 29.8], abs=0.05)

    rig.controller.align_move(0, 0)  # the pad's Home button starts over
    assert rig.controller.status()["align"]["offset"] == [0.0, 0.0]


def test_the_arrows_nudge_at_most_ten_mm(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_move(30, 30)
    with pytest.raises(UserProblem, match=NUDGE_TOO_FAR[:30]):
        rig.controller.align_jog(50, 0)
    assert rig.machine.status()["position"] == pytest.approx([30, 30], abs=0.05)  # nothing moved


def test_lining_up_only_works_while_a_pen_is_asked_for(tmp_path):
    rig = Rig(tmp_path, TWO_COLORS)
    rig.controller.prepare()
    with pytest.raises(UserProblem, match=NOT_NOW):
        rig.controller.align_jog(0.1, 0)


def test_continue_plots_the_new_pen_over_by_the_nudge(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_move(30, 30)
    rig.controller.align_pen(True)
    rig.controller.align_jog(0.5, 0.25)
    dx, dy = rig.controller.status()["align"]["offset"]
    rig.controller.continue_pen()
    rig.wait_until("done")
    assert f"translate({dx:.4f},{dy:.4f})" in rig.controller._plot_svg
    assert rig.controller._plot_svg.count("transform=") == 1  # the black pen's layer stays put
    assert rig.machine.status()["state"] == "ready"
    assert rig.machine.status()["position"] == [0.0, 0.0]


def test_a_pen_that_was_only_moved_plots_where_it_was(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_move(30, 30)
    rig.controller.align_pen(True)
    rig.controller.continue_pen()
    rig.wait_until("done")
    assert "transform=" not in rig.controller._plot_svg


def test_the_next_plot_starts_without_the_last_ones_nudge(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_jog(0.5, 0)
    rig.controller.continue_pen()
    rig.wait_until("done")
    rig.controller.start()
    assert "transform=" not in rig.controller._plot_svg
    assert rig.controller.status()["align"]["offset"] == [0.0, 0.0]
    rig.controller.cancel()


def test_cancel_while_lining_up_brings_the_pen_home(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_move(30, 30)
    rig.controller.align_pen(True)
    rig.controller.cancel()
    assert rig.state() == "ready"
    status = rig.machine.status()
    assert status["state"] == "ready" and status["position"] == [0.0, 0.0]
