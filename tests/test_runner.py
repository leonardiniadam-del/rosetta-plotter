import sys
import threading

import pytest
from lxml import etree
from plotink import ebb_serial
from pyaxidraw import axidraw

from rosetta.compose import ColorGroup
from rosetta.engine import awake
from rosetta.engine import options as engine_options
from rosetta.engine.options import PlotSettings
from rosetta.engine.runner import (
    MESSAGES, PlotOutcome, PlotRunner, Progress, estimate, outcome_for_code, paused_layer,
    set_resume_origin_home,
)
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg
from tests.fake_ebb import FakeEBB, fake_factory, layer_len_mm, layered_svg, skip_engine_waits

SETTINGS = PlotSettings(model=1)

# On layered_svg() layer 1 the pen is down for the first stroke between moves 11 and 17.
MID_STROKE = 14

PERCENT_SIZED_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"/>'


@pytest.fixture(autouse=True)
def fast_engine(monkeypatch):
    skip_engine_waits(monkeypatch)


def _square_plot() -> str:
    square = [(10.0, 10.0), (110.0, 10.0), (110.0, 110.0), (10.0, 110.0), (10.0, 10.0)]
    return plot_svg(get_model(1), [ColorGroup("#000000", [square])])


def _data(svg_text: str) -> dict:
    root = etree.fromstring(svg_text.encode("utf-8"))
    return dict(root.xpath("//*[local-name()='plotdata']")[0].attrib)


class AlwaysSet:
    """Stands in for threading.Event: a pause that's already been requested."""

    def set(self):
        pass

    def is_set(self):
        return True


def _plot_and_pause(moves=MID_STROKE, make_factory=fake_factory, layer=1):
    """Plot a layer on a fake plotter; a second thread presses Pause after `moves` moves."""
    reached, requested = threading.Event(), threading.Event()

    def on_sm(count):
        if count == moves:
            reached.set()
            requested.wait(5)  # hold the fake plotter still until the pause request is in

    ebb = FakeEBB(on_sm=on_sm)
    runner = PlotRunner(factory=make_factory(ebb))

    def press_pause():
        if reached.wait(5):
            runner.pause()
        requested.set()

    presser = threading.Thread(target=press_pause, daemon=True)
    presser.start()
    result = runner.run(layered_svg(), layer, SETTINGS)
    presser.join(5)
    return result, ebb


def _console_free(make_factory):
    """Like the real make_axidraw(): make sure stdout/stderr exist before EMS writes to them."""

    def wrap(ebb):
        make = make_factory(ebb)

        def factory():
            engine_options.ensure_std_streams()
            return make()

        return factory

    return wrap


def _resume(svg_text, ebb=None, layer=1):
    ebb = ebb or FakeEBB()
    return PlotRunner(factory=fake_factory(ebb)).run(svg_text, layer, SETTINGS, resume=True), ebb


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


def test_estimate_counts_only_the_requested_layer():
    result = estimate(layered_svg(), 2, SETTINGS)
    assert result.pendown_m == pytest.approx(layer_len_mm(2) / 1000, abs=0.002)


def test_estimate_of_an_unreadable_plot_is_a_value_error():
    with pytest.raises(ValueError):
        estimate("<svg", 1, SETTINGS)
    with pytest.raises(ValueError):
        estimate(PERCENT_SIZED_SVG, 1, SETTINGS)


def test_preview_run_completes():
    progress = []
    result = PlotRunner(poll_interval=0.001).run(
        _square_plot(), 1, SETTINGS, on_progress=progress.append, preview=True
    )
    assert result.outcome is PlotOutcome.COMPLETED
    assert result.resume_svg is None
    assert progress  # the final sample guarantees one, even for an instant plot
    assert all(isinstance(item, Progress) for item in progress)


def test_pause_then_resume():
    paused = PlotRunner(event_factory=AlwaysSet).run(_square_plot(), 1, SETTINGS, preview=True)
    assert paused.outcome is PlotOutcome.PAUSED
    assert "plotdata" in paused.resume_svg
    resumed = PlotRunner().run(paused.resume_svg, 1, SETTINGS, resume=True, preview=True)
    assert resumed.outcome is PlotOutcome.COMPLETED


def test_full_plot_on_a_fake_plotter_draws_the_layer_and_closes_the_port():
    ebb = FakeEBB()
    result = PlotRunner(factory=fake_factory(ebb)).run(layered_svg(), 1, SETTINGS)
    assert result.outcome is PlotOutcome.COMPLETED
    assert result.resume_svg is None
    assert ebb.pen_cmds[-1][0] == "up"
    assert ebb.closed  # EMS leaves a caller-supplied port open; the runner must not


def test_pause_from_another_thread_lifts_the_pen_and_resumes_the_same_layer():
    paused, ebb = _plot_and_pause()
    assert paused.outcome is PlotOutcome.PAUSED
    after_pause = [command for command, moves in ebb.pen_cmds if moves >= MID_STROKE]
    assert after_pause and after_pause[0] == "up"
    data = _data(paused.resume_svg)
    assert data["layer"] == "1"
    assert int(data["pause_dist"]) > 0

    resumed, resume_ebb = _resume(paused.resume_svg)
    assert resumed.outcome is PlotOutcome.COMPLETED
    assert resumed.resume_svg is None
    assert resume_ebb.pen_cmds  # it really drew the rest


def test_pause_during_the_return_home_leg_still_resumes_only_that_layer():
    svg = layered_svg()
    full = FakeEBB()
    PlotRunner(factory=fake_factory(full)).run(svg, 1, SETTINGS)
    last_pen_move = full.pen_cmds[-1][1]  # the final pen lift comes right after the last stroke
    pause_at = full.sm - 1
    assert pause_at > last_pen_move, "the pause must land on the way Home"

    ebb = FakeEBB()
    runner = PlotRunner(factory=fake_factory(ebb))
    ebb.on_sm = lambda count: runner.pause() if count == pause_at else None
    paused = runner.run(svg, 1, SETTINGS)
    assert paused.outcome is PlotOutcome.PAUSED
    assert _data(paused.resume_svg)["layer"] == "1"  # EMS itself reports -2 (= every layer) here

    resumed, resume_ebb = _resume(paused.resume_svg)
    assert resumed.outcome is PlotOutcome.COMPLETED
    assert [c for c in resume_ebb.pen_cmds if c[0] == "down"] == []  # nothing left to draw


def test_pause_button_pauses_with_resume_data():
    ebb = FakeEBB(button_after_moves=MID_STROKE)
    result = PlotRunner(factory=fake_factory(ebb)).run(layered_svg(), 1, SETTINGS)
    assert result.outcome is PlotOutcome.PAUSED
    assert _data(result.resume_svg)["layer"] == "1"


def test_usb_loss_keeps_resume_data_and_the_plot_resumes_after_homing():
    ebb = FakeEBB(die_after_moves=20)
    result = PlotRunner(factory=fake_factory(ebb)).run(layered_svg(), 1, SETTINGS)
    assert result.outcome is PlotOutcome.DISCONNECTED
    assert _data(result.resume_svg)["layer"] == "1"
    assert ebb.closed

    homed = set_resume_origin_home(result.resume_svg)
    resumed, _ = _resume(homed)
    assert resumed.outcome is PlotOutcome.COMPLETED


def test_pause_without_a_console_still_lifts_the_pen_and_keeps_resume_data(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)  # a windowed build has neither stream
    monkeypatch.setattr(sys, "stderr", None)
    try:
        paused, ebb = _plot_and_pause(make_factory=_console_free(fake_factory))
    finally:
        for stream in (sys.stdout, sys.stderr):
            if stream is not None:
                stream.close()
    assert paused.outcome is PlotOutcome.PAUSED
    assert paused.resume_svg is not None
    assert ebb.pen_cmds[-1][0] == "up"


def test_resume_without_paused_data_is_an_error_and_keeps_the_input():
    svg = _square_plot()
    result = PlotRunner().run(svg, 1, SETTINGS, resume=True, preview=True)
    assert result.outcome is PlotOutcome.ERROR
    assert result.resume_svg == svg
    assert "no paused plot" in result.message.lower()


def test_resume_data_for_every_layer_is_repaired_to_the_requested_layer():
    paused, _ = _plot_and_pause()
    every_layer = paused.resume_svg.replace('layer="1"', 'layer="-2"')
    assert 'layer="-2"' in every_layer
    resumed, resume_ebb = _resume(every_layer)
    assert resumed.outcome is PlotOutcome.COMPLETED
    # The rest of layer 1 is its remaining 8 strokes; every layer would be about three times that.
    assert _pen_downs(resume_ebb) == 8


def _pen_downs(ebb) -> int:
    return sum(1 for command, _ in ebb.pen_cmds if command == "down")


def test_a_run_that_cannot_read_the_plot_is_an_error_not_a_finish():
    broken = PlotRunner().run("<svg", 1, SETTINGS, preview=True)
    assert broken.outcome is PlotOutcome.ERROR
    assert broken.resume_svg is None
    assert broken.message == MESSAGES[PlotOutcome.ERROR]

    # EMS gives up quietly on a page without a size in mm or inches, reporting "stopped == 0".
    unsized = PlotRunner().run(PERCENT_SIZED_SVG, 1, SETTINGS, preview=True)
    assert unsized.outcome is PlotOutcome.ERROR
    assert unsized.resume_svg is None
    assert unsized.message == "This plot couldn't be read."


def test_failed_resume_keeps_the_resume_data_and_hides_the_exception_from_the_message():
    paused, _ = _plot_and_pause()

    class Exploding(axidraw.AxiDraw):
        def plot_run(self, output=False):
            raise RuntimeError("boom")

    result = PlotRunner(factory=Exploding).run(paused.resume_svg, 1, SETTINGS, resume=True)
    assert result.outcome is PlotOutcome.ERROR
    assert result.resume_svg == paused.resume_svg
    assert "boom" not in result.message
    assert "boom" in result.details


def test_resume_with_no_plotter_connected_keeps_the_resume_data(monkeypatch):
    paused, _ = _plot_and_pause()
    monkeypatch.setattr(ebb_serial, "openPort", lambda: None)  # never touch a real plotter
    result = PlotRunner().run(paused.resume_svg, 1, SETTINGS, resume=True)
    assert result.outcome is PlotOutcome.NOT_CONNECTED
    assert result.resume_svg == paused.resume_svg


def test_engine_exception_raises_the_pen_and_closes_the_port(caplog):
    ebb = FakeEBB()

    class Dies(axidraw.AxiDraw):
        def plot_run(self, output=False):
            self.plot_status.port = ebb  # as if EMS had connected...
            self.pen.phys.z_up = False  # ...and lowered the pen...
            raise RuntimeError("serial exploded")  # ...before something went wrong

    result = PlotRunner(factory=Dies).run(layered_svg(), 1, SETTINGS)
    assert result.outcome is PlotOutcome.ERROR
    assert result.resume_svg is None
    assert ebb.pen_cmds == [("up", 0)]
    assert ebb.closed
    assert "serial exploded" in caplog.text


def test_pause_requested_during_setup_is_not_lost():
    runner = PlotRunner()

    class PausesWhileSettingUp(axidraw.AxiDraw):
        def plot_setup(self, svg_input=None, argstrings=None):
            runner.pause()
            super().plot_setup(svg_input, argstrings)

    runner._factory = PausesWhileSettingUp
    result = runner.run(_square_plot(), 1, SETTINGS, preview=True)
    assert result.outcome is PlotOutcome.PAUSED


def test_raising_progress_callback_does_not_stop_the_updates(caplog):
    samples = []

    def on_progress(progress):
        samples.append(progress)
        raise RuntimeError("the screen blew up")

    ebb = FakeEBB(move_sleep=0.002)
    result = PlotRunner(factory=fake_factory(ebb), poll_interval=0.001).run(
        layered_svg(), 1, SETTINGS, on_progress=on_progress
    )
    assert result.outcome is PlotOutcome.COMPLETED
    assert len(samples) > 3
    assert "the screen blew up" in caplog.text


def test_run_snapshots_settings_and_leaves_no_engine_overrides_behind():
    settings = PlotSettings(model=1, pen_down=30)
    made = []

    class Spy(axidraw.AxiDraw):
        def plot_setup(self, svg_input=None, argstrings=None):
            made.append(self)
            settings.pen_down = 60  # the screen edits the settings while the run starts
            super().plot_setup(svg_input, argstrings)

    result = PlotRunner(factory=Spy).run(_square_plot(), 1, settings, preview=True)
    assert result.outcome is PlotOutcome.COMPLETED
    ad = made[0]
    assert ad.options.pen_pos_down == 30
    assert ad.options.rendering == 0
    assert "set_up_pause_receiver" not in ad.__dict__  # the lambda would be a reference cycle


def test_return_home_after_a_pause_then_resume_from_home():
    paused, _ = _plot_and_pause()
    home_ebb = FakeEBB()
    homed = PlotRunner(factory=fake_factory(home_ebb)).return_home(paused.resume_svg, SETTINGS)
    assert homed.outcome is PlotOutcome.COMPLETED
    assert home_ebb.sm > 0
    assert home_ebb.closed
    data = _data(homed.resume_svg)
    assert float(data["last_x"]) == pytest.approx(0, abs=0.1)
    assert float(data["last_y"]) == pytest.approx(0, abs=0.1)
    assert data["layer"] == "1"

    resumed, _ = _resume(homed.resume_svg)
    assert resumed.outcome is PlotOutcome.COMPLETED


def test_return_home_in_preview():
    paused = PlotRunner(event_factory=AlwaysSet).run(_square_plot(), 1, SETTINGS, preview=True)
    homed = PlotRunner().return_home(paused.resume_svg, SETTINGS, preview=True)
    assert homed.outcome is PlotOutcome.COMPLETED
    assert float(_data(homed.resume_svg)["last_x"]) == pytest.approx(0, abs=0.1)


def test_return_home_without_a_paused_plot_is_an_error_and_keeps_the_input():
    svg = _square_plot()
    result = PlotRunner().return_home(svg, SETTINGS, preview=True)
    assert result.outcome is PlotOutcome.ERROR
    assert result.resume_svg == svg
    assert "no paused plot" in result.message.lower()


def test_return_home_with_no_plotter_connected_keeps_the_resume_data(monkeypatch):
    paused, _ = _plot_and_pause()
    monkeypatch.setattr(ebb_serial, "openPort", lambda: None)  # never touch a real plotter
    result = PlotRunner().return_home(paused.resume_svg, SETTINGS)
    assert result.outcome is PlotOutcome.NOT_CONNECTED
    assert result.resume_svg == paused.resume_svg


def test_set_resume_origin_home():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><plotdata last_x="12.5" last_y="4.0"/></svg>'
    updated = set_resume_origin_home(svg)
    assert 'last_x="0"' in updated and 'last_y="0"' in updated


def test_paused_layer_is_the_layer_a_paused_plot_will_finish():
    paused, _ = _plot_and_pause()
    assert paused_layer(paused.resume_svg) == 1
    assert paused_layer(paused.resume_svg.replace('layer="1"', 'layer="2"')) == 2


def test_paused_layer_is_none_when_there_is_nothing_to_resume_or_no_single_layer():
    paused, _ = _plot_and_pause()
    assert paused_layer(layered_svg()) is None  # a plot that never ran has no progress data
    assert paused_layer(paused.resume_svg.replace('layer="1"', 'layer="-2"')) is None  # every layer
    assert paused_layer(paused.resume_svg.replace('pause_dist="', 'pause_dist="-')) is None  # not paused
    assert paused_layer("<svg") is None


def test_set_resume_origin_home_without_data():
    with pytest.raises(ValueError):
        set_resume_origin_home('<svg xmlns="http://www.w3.org/2000/svg"/>')


class RecordingKernel32:
    def __init__(self):
        self.calls = []

    def SetThreadExecutionState(self, flags):
        self.calls.append(flags)


def test_keep_awake_is_reentrant_and_keeps_the_display_on(monkeypatch):
    kernel32 = RecordingKernel32()
    monkeypatch.setattr(awake, "_kernel32", lambda: kernel32)
    wanted = awake.ES_CONTINUOUS | awake.ES_SYSTEM_REQUIRED | awake.ES_DISPLAY_REQUIRED
    with awake.keep_awake():
        with awake.keep_awake():
            pass
        assert kernel32.calls == [wanted]  # the inner exit must not release the outer hold
    assert kernel32.calls == [wanted, awake.ES_CONTINUOUS]


def test_keep_awake_releases_after_an_exception(monkeypatch):
    kernel32 = RecordingKernel32()
    monkeypatch.setattr(awake, "_kernel32", lambda: kernel32)
    with pytest.raises(RuntimeError):
        with awake.keep_awake():
            raise RuntimeError("plot failed")
    assert kernel32.calls[-1] == awake.ES_CONTINUOUS
    with awake.keep_awake():  # and it is usable again afterwards
        pass
    assert len(kernel32.calls) == 4


def test_keep_awake_is_per_thread(monkeypatch):
    kernel32 = RecordingKernel32()
    monkeypatch.setattr(awake, "_kernel32", lambda: kernel32)

    def other_thread():
        with awake.keep_awake():
            pass

    with awake.keep_awake():
        worker = threading.Thread(target=other_thread)
        worker.start()
        worker.join()
    # SetThreadExecutionState is per thread, so each thread sets and clears its own.
    assert len(kernel32.calls) == 4
