import pytest

from rosetta.compose import ColorGroup
from rosetta.engine.awake import keep_awake
from rosetta.engine.options import PlotSettings
from rosetta.engine.runner import (
    PlotOutcome, PlotRunner, Progress, estimate, outcome_for_code, set_resume_origin_home,
)
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg

SETTINGS = PlotSettings(model=1)


def _square_plot() -> str:
    square = [(10.0, 10.0), (110.0, 10.0), (110.0, 110.0), (10.0, 110.0), (10.0, 10.0)]
    return plot_svg(get_model(1), [ColorGroup("#000000", [square])])


class AlwaysSet:
    """Stands in for threading.Event: a pause that's already been requested."""

    def set(self):
        pass

    def is_set(self):
        return True


def test_outcome_codes():
    assert outcome_for_code(0) is PlotOutcome.COMPLETED
    assert outcome_for_code(101) is PlotOutcome.NOT_CONNECTED
    assert outcome_for_code(102) is PlotOutcome.PAUSED
    assert outcome_for_code(103) is PlotOutcome.PAUSED
    assert outcome_for_code(104) is PlotOutcome.DISCONNECTED
    assert outcome_for_code(999) is PlotOutcome.ERROR


def test_estimate_square():
    result = estimate(_square_plot(), 1, SETTINGS)
    assert result.seconds > 1
    assert result.pendown_m == pytest.approx(0.4, abs=0.01)


def test_preview_run_completes():
    progress = []
    result = PlotRunner(poll_interval=0.001).run(
        _square_plot(), 1, SETTINGS, on_progress=progress.append, preview=True
    )
    assert result.outcome is PlotOutcome.COMPLETED
    assert result.resume_svg is None
    assert all(isinstance(item, Progress) for item in progress)


def test_pause_then_resume():
    paused = PlotRunner(event_factory=AlwaysSet).run(_square_plot(), 1, SETTINGS, preview=True)
    assert paused.outcome is PlotOutcome.PAUSED
    assert "plotdata" in paused.resume_svg
    resumed = PlotRunner().run(paused.resume_svg, 1, SETTINGS, resume=True, preview=True)
    assert resumed.outcome is PlotOutcome.COMPLETED


def test_set_resume_origin_home():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><plotdata last_x="12.5" last_y="4.0"/></svg>'
    updated = set_resume_origin_home(svg)
    assert 'last_x="0"' in updated and 'last_y="0"' in updated


def test_set_resume_origin_home_without_data():
    with pytest.raises(ValueError):
        set_resume_origin_home('<svg xmlns="http://www.w3.org/2000/svg"/>')


def test_keep_awake_enters_and_exits():
    with keep_awake():
        pass
