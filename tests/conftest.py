"""Shared test setup.

Adam runs this suite with a real plotter plugged in, so no test may be able to find, open or move it.
The EMS engine finds a plotter by listing the computer's serial ports; that whole search is
switched off for every test. A test that wants a plotter hands the engine a fake one instead
(`options.port = <fake EBB>`, see tests/fake_ebb.py), which never goes near a serial port.
"""
import pytest
import serial
from plotink import ebb_serial

# Everything in plotink.ebb_serial that lists, finds or opens serial ports. EMS (axidrawinternal) calls
# these through the same module object, so one patch covers the pyaxidraw API, the CLI and the runner.
_PORT_SEARCHES = (
    "findPort", "find_named_ebb", "listEBBports", "list_port_info", "list_named_ebbs",
    "openPort", "open_named_port", "testPort",
)


@pytest.fixture(autouse=True)
def no_real_plotter(monkeypatch):
    """No serial port is listed, found or opened. Yields the list of attempts to open one (always empty)."""
    attempts = []

    def finds_nothing(*args, **kwargs):
        return None

    def refuses(*args, **kwargs):
        attempts.append((args, kwargs))
        raise serial.SerialException("The tests may not open a serial port")

    for name in _PORT_SEARCHES:
        monkeypatch.setattr(ebb_serial, name, finds_nothing)
    monkeypatch.setattr(ebb_serial, "comports", lambda *args, **kwargs: [])  # what Windows would list
    monkeypatch.setattr(serial, "Serial", refuses)  # the last line of defence: opening a port itself
    return attempts
