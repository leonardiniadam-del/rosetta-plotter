"""A fake EBB serial port, so the real EMS engine can run non-preview plots in tests."""
import time

import serial
from axidrawinternal import dripfeed, pen_handling, plot_status, serial_utils
from pyaxidraw import axidraw

from rosetta.compose import ColorGroup
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg


class FakeEBB:
    """Speaks just enough EBB protocol for EMS to plot, pause, resume and notice a lost USB cable.

    Hooks: on_sm(count) runs on every real move (a tiny delay each, so another thread can pause
    mid-run); die_after_moves unplugs the "cable"; button_after_moves presses the pause button.
    """

    def __init__(self, die_after_moves=None, move_sleep=0.0005, on_sm=None, button_after_moves=None):
        self.replies = []
        self.log = []
        self.sm = 0
        self.sm_steps1 = 0
        self.sm_steps2 = 0
        self.die_after = die_after_moves
        self.button_after = button_after_moves
        self.dead = False
        self.move_sleep = move_sleep
        self.pen_cmds = []  # ("up" | "down", sm_count_at_that_time)
        self.closed = False
        self.on_sm = on_sm

    # The pyserial surface EMS uses.
    def write(self, data):
        if self.dead:
            raise serial.SerialException("WriteFile failed (fake: device gone)")
        cmd = data.decode("ascii").strip()
        self.log.append(cmd)
        name = cmd.split(",")[0].upper()
        if name == "V":
            self.replies += [b"EBBv13_and_above EB Firmware Version 2.8.1\r\n"]
        elif name == "QB":
            pressed = self.button_after is not None and self.sm >= self.button_after
            self.replies += [b"1\r\n" if pressed else b"0\r\n", b"OK\r\n"]
        elif name == "QC":
            self.replies += [b"0300,0300\r\n", b"OK\r\n"]
        elif name == "QL":
            self.replies += [b"0\r\n", b"OK\r\n"]
        elif name == "QP":
            self.replies += [b"1\r\n", b"OK\r\n"]
        elif name == "QG":
            self.replies += [b"00\r\n"]
        elif name == "PI":
            self.replies += [b"PI,0\r\n"]
        elif name == "SM":
            _, dur, dy, dx = cmd.split(",")
            if int(dur) > 10:  # ignore EMS's tiny "timed pause"
                self.sm += 1
                self.sm_steps1 += int(dy)
                self.sm_steps2 += int(dx)
                if self.on_sm:
                    self.on_sm(self.sm)
                time.sleep(self.move_sleep)
                if self.die_after is not None and self.sm >= self.die_after:
                    self.dead = True
            self.replies += [b"OK\r\n"]
        elif name == "SP":
            self.pen_cmds.append(("up" if cmd.split(",")[1] == "1" else "down", self.sm))
            self.replies += [b"OK\r\n"]
        else:
            self.replies += [b"OK\r\n"]

    def readline(self):
        if self.dead:
            raise serial.SerialException("ReadFile failed (fake: device gone)")
        if self.replies:
            return self.replies.pop(0)
        return b""

    def flushInput(self):
        pass

    def close(self):
        self.closed = True


class IFakeEBB(FakeEBB):
    """FakeEBB plus what the interactive Plotter also asks: firmware, nickname, power, reboot.

    voltage is the motor-supply reading in the QC reply: about 300 with the power adapter in,
    near 0 without it (EMS and Rosetta treat anything under 250 as "unplugged").
    """

    def __init__(self, version="2.8.1", nickname="", voltage=300, **kw):
        super().__init__(**kw)
        self.version = version
        self.nickname = nickname
        self.voltage = voltage

    def write(self, data):
        if self.dead:
            return super().write(data)
        cmd = data.decode("ascii").strip()
        name = cmd.split(",")[0].upper()
        if name == "QC":
            self.log.append(cmd)
            self.replies += [f"0300,{self.voltage:04d}\r\n".encode(), b"OK\r\n"]
            return
        if name == "V":
            self.log.append(cmd)
            self.replies += [f"EBBv13_and_above EB Firmware Version {self.version}\r\n".encode()]
            return
        if name == "QT":
            self.log.append(cmd)
            self.replies += [(self.nickname + "\r\n").encode(), b"OK\r\n"]
            return
        if name == "ST":
            self.log.append(cmd)
            self.nickname = cmd.split(",", 1)[1]
            self.replies += [b"OK\r\n"]
            return
        if name == "RB":
            self.log.append(cmd)
            self.replies += [b"OK\r\n"]
            return
        super().write(data)


class _NoSleepTime:
    """The time module, except that sleep() returns at once."""

    def __getattr__(self, name):
        return getattr(time, name)

    @staticmethod
    def sleep(_seconds):
        pass


class _TickingTime:
    """The time module, except that time() jumps a second forward on every call."""

    def __init__(self):
        self._now = 0.0

    def __getattr__(self, name):
        return getattr(time, name)

    def time(self):
        self._now += 1.0
        return self._now


def skip_engine_waits(monkeypatch):
    """Make fake plots instant and deterministic.

    EMS sleeps in real time while the pen "moves" (about 8 s for a small plot), and it only
    looks at the pause button (and so notices a lost USB cable) every 50 ms. Skip the sleeps
    and make every pause check look at the button.
    """
    for module in (dripfeed, pen_handling, serial_utils):
        monkeypatch.setattr(module, "time", _NoSleepTime())
    monkeypatch.setattr(plot_status, "time", _TickingTime())


def fake_factory(ebb):
    """A runner factory: each call builds a real EMS AxiDraw that talks to `ebb`."""

    class FakeAxiDraw(axidraw.AxiDraw):
        def plot_run(self, output=False):
            self.options.port = ebb  # EMS then uses this "port" instead of looking for a real EBB
            return super().plot_run(output)

    def make():
        return FakeAxiDraw()

    return make


def interactive_factory(ebb):
    """A Plotter factory: each call builds a real EMS AxiDraw whose interactive connect() uses `ebb`."""

    class FakeInteractiveAxiDraw(axidraw.AxiDraw):
        def connect(self):
            self.options.port = ebb  # EMS then uses this "port" instead of looking for a real EBB
            return super().connect()

    return lambda: FakeInteractiveAxiDraw()


def layered_svg(layers=3, n=8):
    """`layers` pen colors; each a bunch of horizontal strokes with different lengths per layer."""
    groups = []
    for k in range(1, layers + 1):
        polys = []
        for i in range(n):
            y = 20.0 + 15 * i + 3 * k
            polys.append([(20.0, y), (20.0 + 40 * k + i, y)])
        groups.append(ColorGroup(["#000000", "#ff0000", "#0000ff", "#00aa00"][k - 1], polys))
    return plot_svg(get_model(1), groups)


def layer_len_mm(k, n=8):
    return sum(40 * k + i for i in range(n))
