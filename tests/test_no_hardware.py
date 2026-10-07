"""The suite can never reach a real plotter, even with one plugged in (see tests/conftest.py)."""
import time

import pytest
import serial
from plotink import ebb_serial

from rosetta.engine.options import PlotSettings
from rosetta.engine.plotter import Plotter
from rosetta.engine.runner import PlotOutcome, PlotRunner
from tests.fake_ebb import FakeEBB, fake_factory, layered_svg, skip_engine_waits

SETTINGS = PlotSettings(model=1)


@pytest.fixture(autouse=True)
def fast_engine(monkeypatch):
    skip_engine_waits(monkeypatch)

# What Windows lists for a real AxiDraw: the port name, a description and the USB IDs.
_PLUGGED_IN_AXIDRAW = [("COM3", "EiBotBoard (COM3)", "USB VID:PID=04D8:FD92 SER=ABC123")]


def test_a_run_with_no_plotter_handed_to_it_finds_none_at_once(no_real_plotter):
    started = time.monotonic()
    result = PlotRunner().run(layered_svg(), 1, SETTINGS, preview=False)
    assert result.outcome is PlotOutcome.NOT_CONNECTED
    assert time.monotonic() - started < 3
    assert no_real_plotter == []  # nothing even tried to open a serial port


def test_a_plotter_that_windows_lists_is_still_never_found_or_opened(monkeypatch, no_real_plotter):
    monkeypatch.setattr(ebb_serial, "comports", lambda *args, **kwargs: list(_PLUGGED_IN_AXIDRAW))
    assert PlotRunner().run(layered_svg(), 1, SETTINGS, preview=False).outcome is PlotOutcome.NOT_CONNECTED
    assert PlotRunner().return_home(_a_paused_plot(), SETTINGS).outcome is PlotOutcome.NOT_CONNECTED
    assert Plotter().connect(SETTINGS) is False
    assert no_real_plotter == []


def test_nothing_in_the_suite_can_open_a_serial_port_itself(no_real_plotter):
    try:
        serial.Serial("COM3")
    except serial.SerialException:
        pass
    else:
        raise AssertionError("a serial port was opened")
    assert len(no_real_plotter) == 1  # and the attempt is recorded


def test_a_fake_plotter_handed_over_as_the_port_still_plots():
    ebb = FakeEBB()
    result = PlotRunner(factory=fake_factory(ebb)).run(layered_svg(), 1, SETTINGS)
    assert result.outcome is PlotOutcome.COMPLETED
    assert ebb.sm > 0


def _a_paused_plot() -> str:
    ebb = FakeEBB(button_after_moves=14)  # the pause button, pressed mid-stroke
    return PlotRunner(factory=fake_factory(ebb)).run(layered_svg(), 1, SETTINGS).resume_svg
