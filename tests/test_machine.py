"""Machine runs the real EMS interactive engine against fake EBBs (tests/fake_ebb.py)."""
import pytest

from rosetta.app.machine import BUSY, NEEDS_MODEL, NO_POWER, NOT_CONNECTED, MachineState
from rosetta.app.settings import SettingsStore
from rosetta.engine.options import Advanced
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
