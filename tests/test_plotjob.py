"""PlotController runs the real EMS engine: the Machine against one fake EBB, plot runs against another."""
import pytest

from rosetta.app.events import RecordingSink
from rosetta.app.plotjob import CLIPPED, NOTHING_TO_PLOT, PREPARE_FIRST, PlotController
from rosetta.app.session import Session
from rosetta.compose import Material
from rosetta.engine.runner import PlotRunner
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
