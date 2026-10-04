from types import SimpleNamespace

import pytest

from rosetta.engine import plotter as plotter_module
from rosetta.engine.identity import Identity
from rosetta.engine.options import PlotSettings
from rosetta.engine.plotter import Plotter


class FakeAD:
    def __init__(self, connect_ok=True):
        self.calls = []
        self.options = SimpleNamespace()
        self.plot_status = SimpleNamespace(port="COM9")
        self._connect_ok = connect_ok
        self._pos = (0.0, 0.0)

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
        self._pos = (x, y)

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


def _connected(model=1):
    fakes = []

    def factory():
        fakes.append(FakeAD())
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


def test_status_queries(fake_ebb):
    plotter, _ = _connected()
    assert plotter.firmware() == "EBBv13_and_above EB Firmware Version 2.8.1"
    assert plotter.power_ok() is True
    assert plotter.read_identity() == Identity(5, 1, "PSU Lab A")


def test_write_identity_reboots_and_drops_session(fake_ebb):
    plotter, _ = _connected()
    assert plotter.write_identity(Identity(2, 1, "PSU Lab A")) is True
    assert ("write", "PSU Lab A m2p1") in fake_ebb
    assert ("reboot", "COM9") in fake_ebb
    assert plotter.connected is False


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


def test_goto_and_jog_stay_within_reach():
    plotter, fakes = _connected(model=1)  # 299.974 x 217.932
    plotter.goto(500, -10)
    assert fakes[0].calls[-1] == ("moveto", 299.974, 0.0)
    plotter.goto(10, 10)
    plotter.jog(5, -20)
    assert fakes[0].calls[-1] == ("moveto", 15.0, 0.0)


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


def test_trace_goes_around_rect_and_home():
    plotter, fakes = _connected()
    plotter.trace((10, 20, 30, 40))
    moves = [call for call in fakes[0].calls if call[0] == "moveto"]
    assert moves == [
        ("moveto", 10, 20), ("moveto", 30, 20), ("moveto", 30, 40),
        ("moveto", 10, 40), ("moveto", 10, 20), ("moveto", 0, 0),
    ]


def test_test_mark_draws_10mm_line_near_corner():
    plotter, fakes = _connected()
    plotter.test_mark(50, 60)
    assert ("lineto", 65, 65) in fakes[0].calls
    assert fakes[0].calls[-1] == ("moveto", 0, 0)


def test_release_for_plot_goes_home_then_disconnects():
    plotter, fakes = _connected()
    plotter.goto(100, 100)
    plotter.release_for_plot()
    assert fakes[0].calls[-2:] == [("moveto", 0, 0), ("disconnect",)]
    assert plotter.connected is False
