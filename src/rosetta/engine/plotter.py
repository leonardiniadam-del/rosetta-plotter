"""Interactive control of a connected plotter: home, jog, pen height, trace, identity.

Uses the EMS interactive context. EMS assumes the pen is at Home (0, 0) when connect()
succeeds, so set_home() reconnects, and release_for_plot() returns Home before a plot
run takes over (spec §6.1).
"""
import dataclasses
import threading
from enum import Enum

from plotink import ebb_motion, ebb_serial

from rosetta.engine.identity import Identity, decode_nickname, encode_nickname
from rosetta.engine.options import PEN_DOWN_MAX, PlotSettings, apply_settings, make_axidraw
from rosetta.models import get_model

MIN_FIRMWARE_FOR_NICKNAME = "2.5.5"
EMS_UNITS_MM = 2

# Hand-placed Home can be a few mm off; never drive the last millimetre toward the far stops.
REACH_SAFETY_MM = 1.0

# A test mark is a line this long, starting this far in from the corner it is given.
MARK_LENGTH_MM = 10.0
MARK_INSET_MM = 5.0


def mark_start(corner_x: float, corner_y: float) -> tuple[float, float]:
    """Where the test mark for this paper corner starts (mm from Home)."""
    return (corner_x + MARK_INSET_MM, corner_y + MARK_INSET_MM)


class PlotterStopped(Exception):
    """The plotter stopped mid-move (pause button or lost USB); its position is no longer known."""


class IdentityWrite(Enum):
    WRITTEN = "written"
    FIRMWARE_TOO_OLD = "firmware_too_old"
    FIRMWARE_UNKNOWN = "firmware_unknown"  # the firmware version couldn't be read
    FAILED = "failed"


class Plotter:
    def __init__(self, factory=make_axidraw):
        self._factory = factory
        self._ad = None
        self._settings: PlotSettings | None = None
        self._pen_is_down = False
        self._pause: threading.Event | None = None

    @property
    def connected(self) -> bool:
        return self._ad is not None

    def connect(self, settings: PlotSettings) -> bool:
        ad = self._factory()
        ad.interactive()
        apply_settings(ad, settings)
        ad.options.units = EMS_UNITS_MM
        pause = threading.Event()
        ad.set_up_pause_receiver(pause)  # EMS checks it before every step of a move
        if not ad.connect():
            return False
        self._ad, self._settings, self._pen_is_down = ad, dataclasses.replace(settings), False
        self._pause = pause
        return True

    def request_pause(self) -> None:
        """Ask the move in progress to stop at its next step (pen up). Safe to call from any thread,
        e.g. for Ctrl+C. The move then raises PlotterStopped, like the pause button does."""
        if self._pause is not None:
            self._pause.set()

    def disconnect(self) -> None:
        """Raise the pen, then let go of the USB port. Safe to call when not connected."""
        ad = self._ad
        if ad is None:
            return
        try:
            try:
                ad.penup()
            except Exception:  # best effort: after a USB drop or a stop, EMS can't lift anything
                pass
            ad.disconnect()
        finally:
            self._ad = None
            self._pause = None
            self._pen_is_down = False

    def firmware(self) -> str:
        return ebb_serial.queryVersion(self._port()).strip()

    def power_ok(self) -> bool:
        return bool(ebb_motion.queryVoltage(self._port(), False))

    def nickname(self) -> str | None:
        """The board's nickname as stored, or None if it has none or can't be read."""
        try:
            return ebb_serial.query_nickname(self._port(), False) or None
        except (UnicodeDecodeError, OSError):  # a foreign, non-ASCII nickname or a flaky port
            return None

    def port_name(self) -> str | None:
        """The serial port's name (e.g. "COM3"), or None if it can't be told."""
        port = self._port()
        return port if isinstance(port, str) else getattr(port, "port", None)

    def read_identity(self) -> Identity | None:
        nickname = self.nickname()
        return decode_nickname(nickname) if nickname else None

    def write_identity(self, identity: Identity) -> IdentityWrite:
        """Store the model on the plotter. Always ends the session; after a successful write
        the board reboots — wait a few seconds before reconnecting."""
        try:
            port = self._port()
            firmware_ok = ebb_serial.min_version(port, MIN_FIRMWARE_FOR_NICKNAME)
            if firmware_ok is None:
                return IdentityWrite.FIRMWARE_UNKNOWN
            if not firmware_ok:
                return IdentityWrite.FIRMWARE_TOO_OLD
            if not ebb_serial.write_nickname(port, encode_nickname(identity)):
                return IdentityWrite.FAILED
            ebb_serial.reboot(port)
            return IdentityWrite.WRITTEN
        finally:
            self.disconnect()

    def motors_off(self) -> None:
        """Lift the pen and let go of the carriage, so it can be slid by hand. EMS never does this
        itself: after a plot, or when the port closes, the motors keep holding the carriage."""
        self.pen_up()
        self._lost_means_stopped(lambda ad: ebb_motion.sendDisableMotors(ad.plot_status.port, False))

    def set_home(self) -> None:
        """The student has slid the pen to Home: reconnect so EMS treats here as (0, 0)."""
        settings = self._settings
        self.disconnect()
        if not self.connect(settings):
            raise RuntimeError("Lost the plotter while setting Home.")

    def position(self) -> tuple[float, float]:
        x, y = self._require().turtle_pos()
        return (x, y)

    def goto(self, x: float, y: float) -> None:
        """Pen-up move to (x, y) mm from Home, kept inside the travel (less a safety margin).

        Raises PlotterStopped if the plotter was paused or lost; EMS would otherwise ignore every
        later move while still reporting the intended position.
        """
        travel_x, travel_y = get_model(self._settings.model).travel_mm
        x = min(max(x, 0.0), travel_x - REACH_SAFETY_MM)
        y = min(max(y, 0.0), travel_y - REACH_SAFETY_MM)
        try:
            self._checked_move(lambda ad: ad.moveto(x, y))
        finally:
            self._pen_is_down = False  # moveto lifts the pen; if it failed, assume up, never down

    def jog(self, dx: float, dy: float) -> None:
        x, y = self.position()
        self.goto(x + dx, y + dy)

    def pen_up(self) -> None:
        self._lost_means_stopped(lambda ad: ad.penup())
        self._pen_is_down = False

    def pen_down(self) -> None:
        self._lost_means_stopped(lambda ad: ad.pendown())
        self._pen_is_down = True

    def set_pen_down_height(self, percent: int) -> None:
        if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= PEN_DOWN_MAX:
            raise ValueError(f"Pen-down height must be a whole number from 0 to {PEN_DOWN_MAX}.")
        ad = self._require()
        self._settings.pen_down = percent
        ad.options.pen_pos_down = percent
        ad.options.pen_pos_up = self._settings.pen_up

        def apply(ad):
            ad.update()
            if self._pen_is_down:  # re-lower so the new height shows on the real pen
                ad.penup()
                ad.pendown()

        self._lost_means_stopped(apply)

    def trace(self, rect: tuple[float, float, float, float]) -> None:
        """Pen up: go around rect so the student sees where the drawing lands, then Home."""
        x0, y0, x1, y1 = rect
        self.pen_up()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)):
            self.goto(x, y)
        self.goto(0.0, 0.0)

    def test_mark(self, corner_x: float, corner_y: float) -> None:
        """A 10 mm line just inside the paper corner nearest Home, then back Home."""
        start_x, start_y = mark_start(corner_x, corner_y)
        self.pen_up()
        self.goto(start_x, start_y)
        self._checked_move(lambda ad: ad.lineto(start_x + MARK_LENGTH_MM, start_y))
        self._pen_is_down = True
        self.pen_up()
        self.goto(0.0, 0.0)

    def release_for_plot(self) -> None:
        """Return Home and let go of the USB port so a plot run can take over."""
        self.pen_up()
        self.goto(0.0, 0.0)
        self.disconnect()

    def _require(self):
        if self._ad is None:
            raise RuntimeError("Not connected to a plotter.")
        return self._ad

    def _lost_means_stopped(self, action) -> None:
        """Run action(ad); EMS's bare RuntimeError("Not connected...") after a USB drop becomes PlotterStopped."""
        ad = self._require()
        try:
            action(ad)
        except RuntimeError as lost:  # EMS: "Not connected to AxiDraw" after a USB drop
            raise PlotterStopped("Lost the connection to the plotter.") from lost

    def _checked_move(self, move) -> None:
        """Run move(ad); turn "the plotter stopped or is gone" into PlotterStopped."""
        ad = self._require()
        self._lost_means_stopped(move)
        if ad.plot_status.stopped:  # 102 pause button, 104 lost USB: EMS now ignores moves
            raise PlotterStopped("The plotter was paused or stopped before the move finished.")

    def _port(self):
        return self._require().plot_status.port
