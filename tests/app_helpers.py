"""Helpers for the rosetta.app tests: a fake plotter that can be plugged in and out, and waiting."""
import time

from rosetta.app.machine import Machine
from rosetta.app.settings import SettingsStore
from rosetta.engine.plotter import Plotter
from tests.fake_ebb import interactive_factory


class Bench:
    """A test bench: plug a fake plotter in (bench.ebb = IFakeEBB(...)) or pull it out (bench.ebb = None).
    Every Plotter the Machine makes talks to whatever is plugged in at that moment."""

    def __init__(self, ebb=None):
        self.ebb = ebb

    def plotter(self) -> Plotter:
        return Plotter(factory=interactive_factory(self.ebb))


def make_machine(tmp_path, ebb=None):
    """(machine, bench, store): settings kept in tmp_path, and no real waiting for reboots."""
    bench = Bench(ebb)
    store = SettingsStore(tmp_path / "settings.json")
    machine = Machine(store, plotter_factory=bench.plotter, sleep=lambda _seconds: None)
    return machine, bench, store


def wait_for(condition, timeout: float = 10.0, interval: float = 0.01) -> None:
    """Wait until condition() is true; fail the test if it never is."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise AssertionError("timed out waiting")
