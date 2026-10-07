"""Machine runs the real EMS interactive engine against fake EBBs (tests/fake_ebb.py)."""
import threading
import time

import pytest

from rosetta.app.machine import (
    BUSY, NEEDS_MODEL, NO_POWER, NOT_CONNECTED, NOT_HOMED, Machine, MachineState,
)
from rosetta.app.settings import SettingsStore
from rosetta.engine.options import Advanced
from rosetta.engine.plotter import Plotter
from rosetta.errors import UserProblem
from tests.app_helpers import make_machine
from tests.fake_ebb import IFakeEBB, skip_engine_waits


@pytest.fixture(autouse=True)
def fast_engine(monkeypatch):
    skip_engine_waits(monkeypatch)


def _plugged(tmp_path, **ebb_args):
    ebb = IFakeEBB(move_sleep=0, **ebb_args)
    machine, bench, store = make_machine(tmp_path, ebb)
    return machine, ebb, bench, store


def test_no_plotter(tmp_path):
    machine, _bench, _store = make_machine(tmp_path)
    assert machine.scan()["state"] == "no_plotter"


def test_a_named_plotter_is_recognized_and_its_carriage_freed(tmp_path):
    machine, ebb, _bench, _store = _plugged(tmp_path, nickname="PSU Lab m5p1")
    status = machine.scan()
    assert status["state"] == "not_homed"
    assert (status["model"], status["model_name"], status["label"]) == (5, "AxiDraw SE/A1", "PSU Lab")
    assert status["power_ok"] is True and "2.8.1" in status["firmware"]
    assert "EM,0,0" in ebb.log  # motors off: the carriage slides by hand
    assert machine.profile_key() == "PSU Lab m5p1"


def test_an_unnamed_plotter_needs_its_model(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path)
    status = machine.scan()
    assert (status["state"], status["model"]) == ("needs_model", None)
    with pytest.raises(UserProblem, match=NEEDS_MODEL):
        machine.set_home()


def test_a_missing_power_adapter_is_reported(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m1p1", voltage=0)
    assert machine.scan()["power_ok"] is False
    with pytest.raises(UserProblem, match=NO_POWER):
        machine.set_home()


def test_identify_names_the_plotter_and_reconnects(tmp_path):
    machine, ebb, _bench, _store = _plugged(tmp_path)
    machine.scan()
    status = machine.identify(5, 1, "PSU Lab")
    assert ebb.nickname == "PSU Lab m5p1"
    assert (status["state"], status["model"], status["nickname"]) == ("not_homed", 5, "PSU Lab m5p1")


def test_identify_on_old_firmware_remembers_the_model_on_this_laptop(tmp_path):
    machine, ebb, _bench, store = _plugged(tmp_path, version="2.4.0")
    ebb.port = "COM7"  # what Plotter.port_name() reads from a real serial port
    machine.scan()
    status = machine.identify(3, 1, "")
    assert (status["state"], status["model"], status["old_firmware"]) == ("not_homed", 3, True)
    assert SettingsStore(store.path).settings.old_firmware["COM7"].model == 3
    assert machine.profile_key() == "port:COM7"


def test_home_makes_the_position_known(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m5p1")
    machine.scan()
    assert machine.set_home()["position"] == [0.0, 0.0]
    status = machine.motors_off()
    assert (status["state"], status["position"]) == ("not_homed", None)


def test_a_busy_plotter_turns_a_second_request_away(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m5p1")
    machine.scan()
    machine._lock.acquire()  # as if a long move were running
    try:
        with pytest.raises(UserProblem, match=BUSY):
            machine.set_home()
        assert machine.scan()["state"] == "not_homed"  # a look while busy just reports
    finally:
        machine._lock.release()


def test_a_pulled_cable_is_noticed(tmp_path):
    machine, ebb, bench, _store = _plugged(tmp_path, nickname="m5p1")
    machine.scan()
    ebb.dead = True
    bench.ebb = None
    assert machine.scan()["state"] == "no_plotter"


class _GoesQuietWhileConnecting(Plotter):
    def connect(self, settings):
        raise IndexError("list index out of range")  # serial_utils, when a port stops answering mid-handshake


def test_a_plotter_that_goes_quiet_while_connecting_counts_as_none(tmp_path):
    machine = Machine(SettingsStore(tmp_path / "settings.json"), plotter_factory=_GoesQuietWhileConnecting)
    assert machine.scan()["state"] == "no_plotter"


def test_a_plotter_that_goes_quiet_while_being_identified_is_let_go(tmp_path, monkeypatch):
    machine, ebb, _bench, _store = _plugged(tmp_path, nickname="m5p1")

    def goes_quiet(_plotter):
        raise IndexError("list index out of range")

    monkeypatch.setattr(Plotter, "firmware", goes_quiet)
    assert machine.scan()["state"] == "no_plotter"
    assert ebb.closed


def test_pen_settings_are_kept_without_a_plotter(tmp_path):
    machine, _bench, _store = make_machine(tmp_path)
    status = machine.set_pen(45, "marker")
    assert (status["pen_down"], status["pen_type"]) == (45, "marker")
    with pytest.raises(ValueError):
        machine.set_pen(81, "marker")


def test_a_pen_height_too_close_to_the_advanced_pen_up_is_refused(tmp_path):
    machine, _bench, _store = make_machine(tmp_path)
    machine.advanced = Advanced(pen_up=50)
    with pytest.raises(UserProblem, match="at least 10 above"):
        machine.set_pen(45, "fineliner")


def test_an_advanced_pen_up_too_close_to_the_pen_down_is_set_aside(tmp_path, caplog):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m1p1")
    machine.advanced = Advanced(pen_up=20)  # kept on this laptop; saved next to another plotter's low pen
    assert machine.scan()["state"] == "not_homed"  # the default pen-down (30) still connects
    assert machine.plot_settings().advanced.pen_up is None
    assert "pen-up height" in caplog.text


def test_plot_settings_need_a_known_plotter(tmp_path):
    machine, _bench, _store = make_machine(tmp_path)
    with pytest.raises(UserProblem, match=NOT_CONNECTED):
        machine.plot_settings()


def test_shutdown_lets_go(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m5p1")
    machine.scan()
    machine.set_home()
    machine.shutdown()
    assert machine.state is MachineState.NO_PLOTTER


def _ready(tmp_path, **ebb_args):
    machine, ebb, bench, _store = _plugged(tmp_path, nickname="Lab m1p1", **ebb_args)
    machine.scan()
    machine.set_home()
    return machine, ebb, bench


def test_goto_and_jog(tmp_path):
    machine, _ebb, _bench = _ready(tmp_path)
    assert machine.goto(50, 20)["position"] == pytest.approx([50, 20])
    assert machine.jog(-10, 5)["position"] == pytest.approx([40, 25])


def test_moves_wait_for_home(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m1p1")
    machine.scan()
    with pytest.raises(UserProblem, match="HOME label"):
        machine.goto(10, 10)


def test_pen_up_and_down(tmp_path):
    machine, ebb, _bench = _ready(tmp_path)
    machine.pen(True)
    assert ebb.pen_cmds[-1][0] == "down"
    machine.pen(False)
    assert ebb.pen_cmds[-1][0] == "up"


def test_the_pen_moves_only_once_homed(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m1p1")
    machine.scan()
    with pytest.raises(UserProblem, match=NOT_HOMED):
        machine.pen(True)


def test_trace_and_test_mark_end_at_home(tmp_path):
    machine, ebb, _bench = _ready(tmp_path)
    machine.goto(30, 30)
    assert machine.trace((10, 10, 60, 40))["position"] == [0.0, 0.0]
    moves = ebb.sm
    assert machine.test_mark(0, 0)["position"] == [0.0, 0.0]
    assert ebb.sm > moves and any(state == "down" for state, _count in ebb.pen_cmds)


def test_a_stopped_move_means_home_is_unknown(tmp_path):
    machine, _ebb, _bench = _ready(tmp_path, button_after_moves=1)  # the plotter's pause button
    with pytest.raises(UserProblem, match="stopped before the move finished"):
        machine.goto(100, 100)
    assert machine.state is MachineState.NOT_HOMED


def test_stop_ends_a_move(tmp_path):
    machine, ebb, _bench = _ready(tmp_path)
    ebb.on_sm = lambda count: count == 3 and machine.request_stop()
    with pytest.raises(UserProblem):
        machine.goto(200, 150)
    assert machine.state is MachineState.NOT_HOMED


def test_a_stop_clicked_while_nothing_moves_does_not_stop_the_next_move(tmp_path):
    machine, _ebb, _bench = _ready(tmp_path)
    machine.request_stop()  # a late click, after the move it was meant for had ended
    assert machine.goto(20, 10)["position"] == pytest.approx([20, 10])
    assert machine.state is MachineState.READY


def test_the_plotter_is_handed_over_for_a_plot_and_taken_back(tmp_path):
    machine, _ebb, _bench = _ready(tmp_path)
    machine.goto(30, 30)
    settings = machine.release_for_plot()
    assert machine.state is MachineState.PLOTTING and settings.model == 1
    with pytest.raises(UserProblem, match="in the middle of a plot. Finish or cancel"):
        machine.goto(5, 5)
    assert machine.after_plot(at_home=True)["state"] == "ready"
    machine.release_for_plot()
    assert machine.after_plot(at_home=False)["state"] == "not_homed"


def _goes_quiet(*_args):
    raise IndexError("list index out of range")  # serial_utils, when a port stops answering


@pytest.mark.parametrize("step, at_home", [("connect", True), ("motors_off", False)])
def test_a_plotter_that_goes_quiet_after_a_plot_is_let_go(tmp_path, monkeypatch, step, at_home):
    machine, _ebb, _bench = _ready(tmp_path)
    machine.release_for_plot()
    with monkeypatch.context() as patch:
        patch.setattr(Plotter, step, _goes_quiet)
        assert machine.after_plot(at_home=at_home)["state"] == "no_plotter"  # not stuck "plotting"
    assert machine.scan()["state"] == "not_homed"  # Step 1 finds it again


def _hold_the_lock_briefly(machine, seconds=0.2) -> threading.Thread:
    """Another thread holds the Machine's lock for a moment, as scan() does while it looks at the plotter."""
    holding = threading.Event()

    def hold():
        with machine._lock:
            holding.set()
            time.sleep(seconds)

    thread = threading.Thread(target=hold)
    thread.start()
    holding.wait()
    return thread


def test_the_end_of_a_plot_waits_for_a_look_at_the_plotter(tmp_path):
    machine, _ebb, _bench = _ready(tmp_path)
    machine.release_for_plot()
    looking = _hold_the_lock_briefly(machine)
    assert machine.release_motors() is True
    looking.join()
    looking = _hold_the_lock_briefly(machine)
    assert machine.after_plot(at_home=True)["state"] == "ready"
    looking.join()


def test_a_plot_needs_the_power_adapter(tmp_path):
    machine, ebb, _bench = _ready(tmp_path)
    ebb.voltage = 0
    with pytest.raises(UserProblem, match=NO_POWER):
        machine.release_for_plot()
    assert machine.state is MachineState.READY


def test_motors_can_be_released_while_a_plot_is_stopped(tmp_path):
    machine, _ebb, bench = _ready(tmp_path)
    machine.release_for_plot()
    assert machine.release_motors() is True
    bench.ebb = None
    assert machine.release_motors() is False
    assert machine.state is MachineState.PLOTTING
