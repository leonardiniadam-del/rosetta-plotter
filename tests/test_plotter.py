from types import SimpleNamespace

import pytest

from rosetta.engine import plotter as plotter_module
from rosetta.engine.identity import Identity
from rosetta.engine.options import PlotSettings
from rosetta.engine.plotter import REACH_SAFETY_MM, IdentityWrite, Plotter, PlotterStopped
from tests.fake_ebb import IFakeEBB, interactive_factory, skip_engine_waits


class FakeAD:
    def __init__(self, connect_ok=True, stop_after_moves=None):
        self.calls = []
        self.options = SimpleNamespace()
        self.plot_status = SimpleNamespace(port="COM9", stopped=0)
        self._connect_ok = connect_ok
        self._pos = (0.0, 0.0)
        self._stop_after_moves = stop_after_moves  # like a press of the pause button
        self._moves = 0

    def interactive(self):
        self.calls.append(("interactive",))

    def connect(self):
        self.calls.append(("connect",))
        self._pos = (0.0, 0.0)
        return self._connect_ok

    def disconnect(self):
        self.calls.append(("disconnect",))

    def moveto(self, x, y):
        self.calls.append(("moveto", round(x, 3), round(y, 3)))
        self._pos = (x, y)  # like EMS, the intended position is kept even when nothing moved
        self._moves += 1
        if self._stop_after_moves is not None and self._moves >= self._stop_after_moves:
            self.plot_status.stopped = 102

    def lineto(self, x, y):
        self.calls.append(("lineto", round(x, 3), round(y, 3)))
        self._pos = (x, y)

    def penup(self):
        self.calls.append(("penup",))

    def pendown(self):
        self.calls.append(("pendown",))

    def update(self):
        self.calls.append(("update",))

    def turtle_pos(self):
        return self._pos


@pytest.fixture
def fake_ebb(monkeypatch):
    log = []
    ebb_motion = SimpleNamespace(
        queryVoltage=lambda port, verbose=True: True,
        sendDisableMotors=lambda port, verbose=True: log.append(("motors_off", port)),
    )
    ebb_serial = SimpleNamespace(
        queryVersion=lambda port: "EBBv13_and_above EB Firmware Version 2.8.1\r\n",
        query_nickname=lambda port, verbose=True: "PSU Lab A m5p1",
        min_version=lambda port, version: True,
        write_nickname=lambda port, name: log.append(("write", name)) or True,
        reboot=lambda port: log.append(("reboot", port)),
    )
    monkeypatch.setattr(plotter_module, "ebb_motion", ebb_motion)
    monkeypatch.setattr(plotter_module, "ebb_serial", ebb_serial)
    return log


def _connected(model=1, **fake_args):
    fakes = []

    def factory():
        fakes.append(FakeAD(**fake_args))
        return fakes[-1]

    plotter = Plotter(factory=factory)
    assert plotter.connect(PlotSettings(model=model))
    return plotter, fakes


def test_connect_uses_mm_and_settings():
    plotter, fakes = _connected(model=5)
    assert fakes[0].options.units == 2
    assert fakes[0].options.model == 5
    assert fakes[0].calls[:2] == [("interactive",), ("connect",)]


def test_connect_failure_returns_false():
    plotter = Plotter(factory=lambda: FakeAD(connect_ok=False))
    assert plotter.connect(PlotSettings(model=1)) is False
    assert plotter.connected is False


def test_connect_keeps_its_own_copy_of_the_settings():
    fakes = []
    plotter = Plotter(factory=lambda: fakes.append(FakeAD()) or fakes[-1])
    settings = PlotSettings(model=1)
    assert plotter.connect(settings)
    settings.pen_down = 77  # the caller changes theirs later
    plotter.set_home()  # reconnects from the plotter's own settings
    assert fakes[1].options.pen_pos_down == 30


def test_status_queries(fake_ebb):
    plotter, _ = _connected()
    assert plotter.firmware() == "EBBv13_and_above EB Firmware Version 2.8.1"
    assert plotter.power_ok() is True
    assert plotter.read_identity() == Identity(5, 1, "PSU Lab A")


def test_write_identity_reboots_and_drops_session(fake_ebb):
    plotter, fakes = _connected()
    assert plotter.write_identity(Identity(2, 1, "PSU Lab A")) is IdentityWrite.WRITTEN
    assert ("write", "PSU Lab A m2p1") in fake_ebb
    assert ("reboot", "COM9") in fake_ebb
    assert fakes[0].calls[-1] == ("disconnect",)
    assert plotter.connected is False


def test_write_identity_refuses_old_firmware_and_still_ends_the_session(fake_ebb, monkeypatch):
    monkeypatch.setattr(plotter_module.ebb_serial, "min_version", lambda port, version: False)
    plotter, fakes = _connected()
    assert plotter.write_identity(Identity(2, 1, "PSU Lab A")) is IdentityWrite.FIRMWARE_TOO_OLD
    assert fake_ebb == []  # nothing written, no reboot
    assert fakes[0].calls[-1] == ("disconnect",)
    assert plotter.connected is False


def test_write_identity_with_unreadable_firmware_is_not_called_too_old(fake_ebb, monkeypatch):
    monkeypatch.setattr(plotter_module.ebb_serial, "min_version", lambda port, version: None)
    plotter, fakes = _connected()
    assert plotter.write_identity(Identity(2, 1, "PSU Lab A")) is IdentityWrite.FIRMWARE_UNKNOWN
    assert fake_ebb == []
    assert fakes[0].calls[-1] == ("disconnect",)
    assert plotter.connected is False


@pytest.mark.parametrize("answer", [False, None])
def test_failed_nickname_write_does_not_reboot_but_ends_the_session(fake_ebb, monkeypatch, answer):
    monkeypatch.setattr(plotter_module.ebb_serial, "write_nickname", lambda port, name: answer)
    plotter, fakes = _connected()
    assert plotter.write_identity(Identity(2, 1, "PSU Lab A")) is IdentityWrite.FAILED
    assert not any(entry[0] == "reboot" for entry in fake_ebb)
    assert fakes[0].calls[-1] == ("disconnect",)
    assert plotter.connected is False


def test_nickname_is_the_raw_text_or_none(fake_ebb, monkeypatch):
    plotter, _ = _connected()
    assert plotter.nickname() == "PSU Lab A m5p1"
    monkeypatch.setattr(plotter_module.ebb_serial, "query_nickname", lambda port, verbose=True: None)
    assert plotter.nickname() is None
    monkeypatch.setattr(plotter_module.ebb_serial, "query_nickname", lambda port, verbose=True: "")
    assert plotter.nickname() is None


@pytest.mark.parametrize("error", [UnicodeDecodeError("ascii", b"\xff", 0, 1, "not ascii"), OSError("port gone")])
def test_unreadable_nickname_is_none(fake_ebb, monkeypatch, error):
    def broken(port, verbose=True):
        raise error

    monkeypatch.setattr(plotter_module.ebb_serial, "query_nickname", broken)
    plotter, _ = _connected()
    assert plotter.nickname() is None


def test_motors_off_lifts_pen_first(fake_ebb):
    plotter, fakes = _connected()
    plotter.motors_off()
    assert fakes[0].calls[-1] == ("penup",)
    assert fake_ebb[-1] == ("motors_off", "COM9")


def test_set_home_reconnects():
    plotter, fakes = _connected()
    plotter.set_home()
    assert len(fakes) == 2
    assert ("disconnect",) in fakes[0].calls
    assert plotter.connected


def test_disconnect_raises_the_pen_before_letting_go():
    plotter, fakes = _connected()
    plotter.pen_down()
    plotter.disconnect()
    assert fakes[0].calls[-3:] == [("pendown",), ("penup",), ("disconnect",)]
    assert plotter.connected is False


def test_disconnect_still_lets_go_when_the_pen_cannot_be_raised():
    plotter, fakes = _connected()

    def refuse():
        raise RuntimeError("Not connected to AxiDraw")  # what EMS says after a USB drop

    fakes[0].penup = refuse
    plotter.disconnect()
    assert fakes[0].calls[-1] == ("disconnect",)
    assert plotter.connected is False


def test_disconnect_when_not_connected_does_nothing():
    plotter = Plotter(factory=FakeAD)
    plotter.disconnect()
    assert plotter.connected is False


def test_goto_and_jog_stay_within_reach():
    plotter, fakes = _connected(model=1)  # 299.974 x 217.932
    plotter.goto(500, -10)
    assert fakes[0].calls[-1] == ("moveto", round(299.974 - REACH_SAFETY_MM, 3), 0.0)
    plotter.goto(-5, 500)
    assert fakes[0].calls[-1] == ("moveto", 0.0, round(217.932 - REACH_SAFETY_MM, 3))
    plotter.goto(10, 10)
    plotter.jog(5, -20)
    assert fakes[0].calls[-1] == ("moveto", 15.0, 0.0)


def test_goto_that_the_engine_cannot_send_means_the_plotter_was_lost():
    plotter, fakes = _connected()

    def lost(x, y):
        raise RuntimeError("Not connected to AxiDraw")

    fakes[0].moveto = lost
    with pytest.raises(PlotterStopped, match="Lost the connection"):
        plotter.goto(10, 10)


@pytest.mark.parametrize("broken, call", [
    ("penup", lambda plotter: plotter.pen_up()),
    ("pendown", lambda plotter: plotter.pen_down()),
    ("update", lambda plotter: plotter.set_pen_down_height(40)),
    ("penup", lambda plotter: plotter.motors_off()),  # motors_off lifts the pen first
])
def test_pen_and_motor_commands_after_a_usb_loss_say_the_connection_was_lost(fake_ebb, broken, call):
    plotter, fakes = _connected()

    def lost(*args):
        raise RuntimeError("Not connected to AxiDraw")  # what EMS says after a USB drop

    setattr(fakes[0], broken, lost)
    with pytest.raises(PlotterStopped, match="Lost the connection to the plotter."):
        call(plotter)
    assert ("motors_off", "COM9") not in fake_ebb  # it didn't pretend the motors were released


def test_goto_after_a_pause_raises_instead_of_pretending_to_move():
    plotter, fakes = _connected(stop_after_moves=1)
    with pytest.raises(PlotterStopped, match="paused or stopped"):
        plotter.goto(10, 10)
    with pytest.raises(PlotterStopped):  # EMS now ignores every move; so must we trust nothing
        plotter.jog(5, 5)


def test_unreadable_nickname_reads_as_unknown(fake_ebb, monkeypatch):
    def garbled(port, verbose=True):
        raise UnicodeDecodeError("ascii", b"\xff", 0, 1, "not ascii")

    monkeypatch.setattr(plotter_module.ebb_serial, "query_nickname", garbled)
    plotter, _ = _connected()
    assert plotter.read_identity() is None


@pytest.mark.parametrize("percent", [-1, 81, 30.5, True])
def test_pen_height_outside_the_safe_range_is_refused(percent):
    plotter, _ = _connected()
    with pytest.raises(ValueError):
        plotter.set_pen_down_height(percent)


def test_pen_height_updates_live_when_pen_is_down():
    plotter, fakes = _connected()
    plotter.pen_down()
    plotter.set_pen_down_height(45)
    assert fakes[0].options.pen_pos_down == 45
    assert fakes[0].options.pen_pos_up == 65
    assert fakes[0].calls[-3:] == [("update",), ("penup",), ("pendown",)]


def test_pen_height_does_not_lower_a_pen_that_a_move_lifted():
    plotter, fakes = _connected()
    plotter.pen_down()
    plotter.jog(1, 0)  # EMS moveto lifts the pen
    plotter.set_pen_down_height(40)
    assert fakes[0].calls[-1] == ("update",)


def test_pen_height_leaves_the_callers_settings_alone():
    fake = FakeAD()
    plotter = Plotter(factory=lambda: fake)
    settings = PlotSettings(model=1)
    assert plotter.connect(settings)
    plotter.set_pen_down_height(45)
    assert settings.pen_down == 30
    assert fake.options.pen_pos_down == 45


def test_trace_goes_around_rect_and_home():
    plotter, fakes = _connected()
    plotter.trace((10, 20, 30, 40))
    moves = [call for call in fakes[0].calls if call[0] == "moveto"]
    assert moves == [
        ("moveto", 10, 20), ("moveto", 30, 20), ("moveto", 30, 40),
        ("moveto", 10, 40), ("moveto", 10, 20), ("moveto", 0, 0),
    ]


def test_trace_stops_for_good_when_the_plotter_is_paused():
    plotter, fakes = _connected(stop_after_moves=2)
    with pytest.raises(PlotterStopped):
        plotter.trace((10, 20, 30, 40))
    moves = [call for call in fakes[0].calls if call[0] == "moveto"]
    assert moves == [("moveto", 10, 20), ("moveto", 30, 20)]  # no more moves, no "back Home"


def test_test_mark_draws_10mm_line_near_corner():
    plotter, fakes = _connected()
    plotter.test_mark(50, 60)
    assert ("lineto", 65, 65) in fakes[0].calls
    assert fakes[0].calls[-1] == ("moveto", 0, 0)


def test_test_mark_stops_when_the_plotter_is_paused_mid_line():
    plotter, fakes = _connected()

    def paused_line(x, y):
        fakes[0].calls.append(("lineto", round(x, 3), round(y, 3)))
        fakes[0].plot_status.stopped = 102

    fakes[0].lineto = paused_line
    with pytest.raises(PlotterStopped):
        plotter.test_mark(50, 60)
    assert ("lineto", 65, 65) in fakes[0].calls
    assert ("moveto", 0, 0) not in fakes[0].calls  # it did not claim to go Home


def test_release_for_plot_goes_home_then_disconnects():
    plotter, fakes = _connected()
    plotter.goto(100, 100)
    plotter.release_for_plot()
    assert fakes[0].calls[-3:] == [("moveto", 0, 0), ("penup",), ("disconnect",)]
    assert plotter.connected is False


# The same, against the real EMS interactive engine talking to a fake EBB.


def _on_real_ems(monkeypatch, **ebb_args):
    skip_engine_waits(monkeypatch)
    ebb = IFakeEBB(move_sleep=0, **ebb_args)
    plotter = Plotter(factory=interactive_factory(ebb))
    assert plotter.connect(PlotSettings(model=1))
    return plotter, ebb


def test_real_ems_disconnect_closes_the_port(monkeypatch):
    plotter, ebb = _on_real_ems(monkeypatch)
    assert not ebb.closed
    plotter.disconnect()
    assert ebb.closed
    assert plotter.connected is False


def test_real_ems_motors_off_sends_the_disable_command(monkeypatch):
    plotter, ebb = _on_real_ems(monkeypatch)
    plotter.motors_off()
    assert "EM,0,0" in ebb.log
    plotter.disconnect()


def test_real_ems_write_identity_stores_the_name_reboots_and_closes_the_port(monkeypatch):
    plotter, ebb = _on_real_ems(monkeypatch)
    assert plotter.write_identity(Identity(5, 1, "PSU Lab")) is IdentityWrite.WRITTEN
    assert any(cmd.startswith("ST,") and "PSU Lab m5p1" in cmd for cmd in ebb.log)
    assert any(cmd.startswith("RB") for cmd in ebb.log)
    assert ebb.closed
    assert plotter.connected is False


def test_real_ems_write_identity_on_old_firmware_writes_nothing_and_closes_the_port(monkeypatch):
    skip_engine_waits(monkeypatch)
    ebb = IFakeEBB(version="2.4.0", move_sleep=0)
    plotter = Plotter(factory=interactive_factory(ebb))
    assert plotter.connect(PlotSettings(model=1))
    assert plotter.write_identity(Identity(5, 1, "PSU Lab")) is IdentityWrite.FIRMWARE_TOO_OLD
    assert not any(cmd.startswith(("ST,", "RB")) for cmd in ebb.log)
    assert ebb.closed


def test_real_ems_reads_the_nickname_and_the_identity(monkeypatch):
    plotter, _ebb = _on_real_ems(monkeypatch, nickname="PSU Lab m5p1")
    assert plotter.nickname() == "PSU Lab m5p1"
    assert plotter.read_identity() == Identity(5, 1, "PSU Lab")
    plotter.disconnect()


def test_real_ems_reads_whether_the_power_adapter_is_plugged_in(monkeypatch):
    plugged, _ = _on_real_ems(monkeypatch)
    assert plugged.power_ok() is True
    plugged.disconnect()
    unplugged, _ = _on_real_ems(monkeypatch, voltage=0)
    assert unplugged.power_ok() is False
    unplugged.disconnect()


def test_real_ems_blank_nickname_reads_as_none(monkeypatch):
    plotter, _ebb = _on_real_ems(monkeypatch)
    assert plotter.nickname() is None
    assert plotter.read_identity() is None
    plotter.disconnect()


def test_real_ems_trace_that_completes_ends_at_home(monkeypatch):
    plotter, ebb = _on_real_ems(monkeypatch)
    plotter.trace((50, 40, 250, 180))
    assert ebb.sm > 0
    x, y = plotter.position()
    assert abs(x) < 1e-3 and abs(y) < 1e-3
    plotter.disconnect()


def test_real_ems_pause_button_during_a_trace_is_reported_not_swallowed(monkeypatch):
    plotter, ebb = _on_real_ems(monkeypatch, button_after_moves=40)
    with pytest.raises(PlotterStopped):
        plotter.trace((50, 40, 250, 180))
    moves_when_stopped = ebb.sm
    with pytest.raises(PlotterStopped):  # EMS ignores moves from here on; Rosetta must not believe them
        plotter.goto(100, 100)
    assert ebb.sm == moves_when_stopped
    plotter.disconnect()
    assert ebb.closed


def test_real_ems_set_home_gets_a_paused_plotter_moving_again(monkeypatch):
    plotter, ebb = _on_real_ems(monkeypatch, button_after_moves=40)
    with pytest.raises(PlotterStopped):
        plotter.trace((50, 40, 250, 180))
    ebb.button_after = None  # the student lets go of the button and slides the pen Home again
    plotter.set_home()
    moves_before = ebb.sm
    plotter.goto(100, 100)
    assert ebb.sm > moves_before
    plotter.disconnect()


def test_real_ems_lost_usb_cable_during_a_trace_is_reported(monkeypatch):
    plotter, ebb = _on_real_ems(monkeypatch, die_after_moves=40)
    with pytest.raises(PlotterStopped):
        plotter.trace((50, 40, 250, 180))
    with pytest.raises(PlotterStopped, match="Lost the connection"):  # EMS: "Not connected to AxiDraw"
        plotter.goto(100, 100)
    for command in (plotter.pen_up, plotter.pen_down, plotter.motors_off, lambda: plotter.set_pen_down_height(40)):
        with pytest.raises(PlotterStopped, match="Lost the connection"):  # not EMS's bare RuntimeError
            command()
    plotter.disconnect()
    assert ebb.closed
