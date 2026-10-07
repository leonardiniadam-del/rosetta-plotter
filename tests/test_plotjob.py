"""PlotController runs the real EMS engine: the Machine against one fake EBB, plot runs against another."""
import pytest

from rosetta.app.events import RecordingSink
from rosetta.app.plotjob import (
    CLIPPED, FINISH_FIRST, HOME_UNKNOWN, NOT_NOW, NOTHING_TO_PLOT, PREPARE_FIRST, PlotController,
)
from rosetta.app.session import Session
from rosetta.compose import Material
from rosetta.engine.runner import PlotRunner, Progress
from rosetta.errors import UserProblem
from tests.app_helpers import make_machine, wait_for
from tests.fake_ebb import FakeEBB, IFakeEBB, fake_factory, skip_engine_waits

LETTER = Material(0.0, 0.0, 279.4, 215.9)
ONE_COLOR = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">
<path d="M10 10 H90 V50 H10 Z" stroke="#000000" fill="none"/>
</svg>"""
TWO_COLORS = ONE_COLOR.replace("</svg>", '<path d="M20 30 H80" stroke="#ff0000" fill="none"/></svg>')


@pytest.fixture(autouse=True)
def fast_engine(monkeypatch):
    skip_engine_waits(monkeypatch)


class Rig:
    """A homed Machine on one fake plotter, plot runs on another, and a controller over both.
    Replace rig.run_ebb to change what the next plot run finds (None: no plotter at all)."""

    def __init__(self, tmp_path, drawing=ONE_COLOR, run_ebb=None):
        self.plotter_ebb = IFakeEBB(nickname="Lab m1p1", move_sleep=0)
        self.machine, self.bench, _store = make_machine(tmp_path, self.plotter_ebb)
        self.machine.scan()
        self.machine.set_home()
        self.session = Session(LETTER)
        art = tmp_path / "art.svg"
        art.write_text(drawing, encoding="utf-8")
        self.session.add(art)
        self.run_ebb = run_ebb or FakeEBB(move_sleep=0)
        self.sink = RecordingSink()
        runner = PlotRunner(factory=lambda: fake_factory(self.run_ebb)(), poll_interval=0.001)
        self.controller = PlotController(self.machine, self.session, self.sink, runner_factory=lambda: runner)

    def state(self) -> str:
        return self.controller.status()["state"]

    def wait_until(self, state: str) -> None:
        wait_for(lambda: self.state() == state)


def test_prepare_plans_every_pen(tmp_path):
    rig = Rig(tmp_path, TWO_COLORS)
    summary = rig.controller.prepare()
    assert [(layer["layer"], layer["name"]) for layer in summary["layers"]] == [(1, "black"), (2, "red")]
    assert summary["total_seconds"] > 0
    assert summary["layers"][0]["path"][0]["down"] is False  # it sets off from Home, pen up
    assert rig.state() == "ready"
    assert rig.sink.named("plot_state")[-1]["actions"] == ["trace", "start"]


def test_prepare_with_nothing_on_the_paper(tmp_path):
    rig = Rig(tmp_path)
    rig.session.clear()
    with pytest.raises(UserProblem, match=NOTHING_TO_PLOT):
        rig.controller.prepare()


def test_prepare_warns_about_lines_off_the_paper(tmp_path):
    rig = Rig(tmp_path)
    rig.session.place(rig.session.pieces[0].id, 250, 10, 1, 0)  # hangs off the paper's far edge
    assert CLIPPED in rig.controller.prepare()["warnings"]


def test_a_one_pen_plot_runs_to_done(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.controller.start()
    rig.wait_until("done")
    assert rig.run_ebb.sm > 0
    assert rig.machine.status()["state"] == "ready"
    progress = rig.sink.named("plot_progress")
    assert progress and progress[-1]["fraction"] == pytest.approx(1.0, abs=0.01)


def test_each_pen_is_asked_for(tmp_path):
    rig = Rig(tmp_path, TWO_COLORS)
    rig.controller.prepare()
    rig.controller.start()
    assert rig.state() == "load_pen" and "black pen" in rig.controller.status()["message"]
    rig.controller.continue_pen()
    rig.wait_until("load_pen")
    assert "red pen in the holder (2 of 2)" in rig.controller.status()["message"]
    rig.controller.continue_pen()
    rig.wait_until("done")


def test_plot_another_copy(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.controller.start()
    rig.wait_until("done")
    moves = rig.run_ebb.sm
    rig.controller.start()
    wait_for(lambda: rig.run_ebb.sm > moves and rig.state() == "done")


def test_no_power_means_no_plot(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.plotter_ebb.voltage = 0
    with pytest.raises(UserProblem, match="power adapter"):
        rig.controller.start()
    assert rig.state() == "ready"


def test_changes_make_the_prepared_plot_stale(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.controller.invalidate()
    assert rig.state() == "idle"
    with pytest.raises(UserProblem, match=PREPARE_FIRST):
        rig.controller.start()


def test_trace_goes_around_the_drawing_and_home(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    moves = rig.plotter_ebb.sm
    assert rig.controller.trace()["position"] == [0.0, 0.0]
    assert rig.plotter_ebb.sm > moves and rig.state() == "ready"


def test_a_run_that_finds_no_plotter_has_moved_nothing(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.run_ebb = None
    rig.controller.start()
    rig.wait_until("not_connected")
    assert rig.controller.status()["actions"] == ["retry", "cancel"]


def _pause_after(rig, moves):
    """Press the app's Pause button once the plot has made this many moves."""
    rig.run_ebb.on_sm = lambda count: count == moves and rig.controller.pause()


def test_pause_then_resume_finishes_the_plot(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    _pause_after(rig, 5)
    rig.controller.start()
    rig.wait_until("paused")
    assert rig.controller.status()["actions"] == ["resume", "home", "cancel"]
    with pytest.raises(UserProblem, match=FINISH_FIRST):
        rig.controller.prepare()
    rig.controller.resume()
    rig.wait_until("done")


def test_return_home_while_paused(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    _pause_after(rig, 5)
    rig.controller.start()
    rig.wait_until("paused")
    rig.controller.home()
    rig.wait_until("paused_at_home")
    rig.controller.resume()
    rig.wait_until("done")


def test_cancel_while_paused_asks_for_a_new_home(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    _pause_after(rig, 5)
    rig.controller.start()
    rig.wait_until("paused")
    rig.controller.cancel()
    assert rig.state() == "ready" and HOME_UNKNOWN in rig.controller.status()["message"]
    assert rig.machine.status()["state"] == "not_homed"


def test_cancel_at_a_pen_change_keeps_home(tmp_path):
    rig = Rig(tmp_path, TWO_COLORS)
    rig.controller.prepare()
    rig.controller.start()
    rig.controller.cancel()
    assert rig.state() == "ready" and rig.machine.status()["state"] == "ready"


def test_a_pulled_cable_resumes_after_a_slide_home(tmp_path):
    rig = Rig(tmp_path, run_ebb=FakeEBB(die_after_moves=5, move_sleep=0))
    rig.controller.prepare()
    rig.controller.start()
    rig.wait_until("reconnect")
    assert "Plotter disconnected" in rig.controller.status()["message"]
    rig.run_ebb = FakeEBB(move_sleep=0)  # plugged back in
    rig.controller.reconnect()
    assert rig.state() == "slide_home"
    rig.controller.rehomed()
    assert rig.state() == "paused_at_home"
    rig.controller.resume()
    rig.wait_until("done")


def test_reconnect_waits_until_the_plotter_is_back(tmp_path):
    rig = Rig(tmp_path, run_ebb=FakeEBB(die_after_moves=5, move_sleep=0))
    rig.controller.prepare()
    rig.controller.start()
    rig.wait_until("reconnect")
    rig.bench.ebb = None  # still unplugged
    rig.controller.reconnect()
    assert rig.state() == "reconnect" and "Still no plotter" in rig.controller.status()["message"]


def test_retry_after_no_plotter_was_found(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.run_ebb = None
    rig.controller.start()
    rig.wait_until("not_connected")
    rig.run_ebb = FakeEBB(move_sleep=0)
    rig.controller.retry()
    rig.wait_until("done")


def test_a_pause_asked_for_before_the_run_listens_is_asked_again(tmp_path):
    class CountingRunner:
        pauses = 0

        def pause(self):
            self.pauses += 1

    rig = Rig(tmp_path)
    runner = CountingRunner()
    controller = PlotController(rig.machine, rig.session, RecordingSink(), runner_factory=lambda: runner)
    controller.prepare()
    controller._pause_wanted = True  # what pause() leaves when the run wasn't listening yet
    controller._on_progress(Progress(1.0, 2.0, 3.0))
    assert runner.pauses == 1


def test_buttons_that_do_not_fit_the_state_are_refused(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    for action in (rig.controller.resume, rig.controller.home, rig.controller.cancel,
                   rig.controller.continue_pen, rig.controller.reconnect, rig.controller.rehomed,
                   rig.controller.retry):
        with pytest.raises(UserProblem, match=NOT_NOW):
            action()
    rig.controller.pause()  # a late Pause click is harmless
    assert rig.state() == "ready"
