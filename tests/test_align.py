"""At a pen change, the new pen is lined up with lines already drawn, and its layer plots that far over."""
import pytest

from rosetta.app.plotjob import GO_TO_LINE_FIRST, NO_LINES_YET, NUDGE_TOO_FAR
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


def test_the_first_pen_has_no_line_to_go_to(tmp_path):
    rig = Rig(tmp_path, TWO_COLORS)
    rig.controller.prepare()
    rig.controller.start()
    assert rig.controller.status()["align"]["available"] is False
    with pytest.raises(UserProblem, match=NO_LINES_YET):
        rig.controller.align_goto()


def test_the_pen_goes_to_a_drawn_line_and_nudges_add_up(tmp_path):
    rig = _at_second_pen(tmp_path)
    assert rig.controller.status()["align"] == {"available": True, "target": None, "offset": [0.0, 0.0]}
    with pytest.raises(UserProblem, match=GO_TO_LINE_FIRST):
        rig.controller.align_jog(0.1, 0)

    rig.controller.align_goto()
    target = rig.controller.status()["align"]["target"]
    drawn = [layer for layer in rig.controller.summary()["layers"] if layer["name"] == "black"][0]
    first_line = next(run for run in drawn["path"] if run["down"])
    assert target == pytest.approx(first_line["points"][:2], abs=0.01)
    assert rig.machine.status()["position"] == pytest.approx(target, abs=0.05)

    rig.controller.align_pen(True)
    rig.controller.align_jog(0.3, 0)
    rig.controller.align_jog(0, -0.2)
    assert rig.controller.status()["align"]["offset"] == pytest.approx([0.3, -0.2], abs=0.02)
    assert rig.machine.status()["position"] == pytest.approx([target[0] + 0.3, target[1] - 0.2], abs=0.05)

    rig.controller.align_reset()
    assert rig.controller.status()["align"]["offset"] == [0.0, 0.0]
    with pytest.raises(UserProblem, match=NUDGE_TOO_FAR[:20]):
        rig.controller.align_jog(11, 0)


def test_continue_plots_the_new_pen_over_by_the_nudge(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_goto()
    rig.controller.align_pen(True)
    rig.controller.align_jog(0.5, 0.25)
    dx, dy = rig.controller.status()["align"]["offset"]
    rig.controller.continue_pen()
    rig.wait_until("done")
    assert f"translate({dx:.4f},{dy:.4f})" in rig.controller._plot_svg
    assert rig.controller._plot_svg.count("transform=") == 1  # the black pen's layer stays put
    assert rig.machine.status()["state"] == "ready"
    assert rig.machine.status()["position"] == [0.0, 0.0]


def test_a_pen_that_was_not_nudged_plots_where_it_was(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_goto()
    rig.controller.continue_pen()
    rig.wait_until("done")
    assert "transform=" not in rig.controller._plot_svg


def test_the_next_plot_starts_without_the_last_ones_nudge(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_goto()
    rig.controller.align_jog(0.5, 0)
    rig.controller.continue_pen()
    rig.wait_until("done")
    rig.controller.start()
    assert "transform=" not in rig.controller._plot_svg
    rig.controller.cancel()


def test_cancel_while_lining_up_brings_the_pen_home(tmp_path):
    rig = _at_second_pen(tmp_path)
    rig.controller.align_goto()
    rig.controller.align_pen(True)
    rig.controller.cancel()
    assert rig.state() == "ready"
    status = rig.machine.status()
    assert status["state"] == "ready" and status["position"] == [0.0, 0.0]
