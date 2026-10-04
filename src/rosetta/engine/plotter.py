"""Interactive control of a connected plotter: home, jog, pen height, trace, identity.

Uses the EMS interactive context. EMS assumes the pen is at Home (0, 0) when connect()
succeeds, so set_home() reconnects, and release_for_plot() returns Home before a plot
run takes over (spec §6.1).
"""
from plotink import ebb_motion, ebb_serial

from rosetta.engine.identity import Identity, decode_nickname, encode_nickname
from rosetta.engine.options import PEN_DOWN_MAX, PlotSettings, apply_settings, make_axidraw
from rosetta.models import get_model

MIN_FIRMWARE_FOR_NICKNAME = "2.5.5"
EMS_UNITS_MM = 2


class Plotter:
    def __init__(self, factory=make_axidraw):
        self._factory = factory
        self._ad = None
        self._settings: PlotSettings | None = None
        self._pen_is_down = False

    @property
    def connected(self) -> bool:
        return self._ad is not None

    def connect(self, settings: PlotSettings) -> bool:
        ad = self._factory()
        ad.interactive()
        apply_settings(ad, settings)
        ad.options.units = EMS_UNITS_MM
        if not ad.connect():
            return False
        self._ad, self._settings, self._pen_is_down = ad, settings, False
        return True

    def disconnect(self) -> None:
        if self._ad is not None:
            try:
                self._ad.disconnect()
            finally:
                self._ad = None

    def firmware(self) -> str:
        return ebb_serial.queryVersion(self._port()).strip()

    def power_ok(self) -> bool:
        return bool(ebb_motion.queryVoltage(self._port(), False))

    def read_identity(self) -> Identity | None:
        try:
            nickname = ebb_serial.query_nickname(self._port(), False)
        except (UnicodeDecodeError, OSError):  # a foreign, non-ASCII nickname or a flaky port
            return None
        return decode_nickname(nickname) if nickname else None

    def write_identity(self, identity: Identity) -> bool:
        """Store the model on the plotter. The board reboots, so this session ends."""
        port = self._port()
        if not ebb_serial.min_version(port, MIN_FIRMWARE_FOR_NICKNAME):
            return False
        written = bool(ebb_serial.write_nickname(port, encode_nickname(identity)))
        if written:
            ebb_serial.reboot(port)
        self._ad = None
        return written

    def motors_off(self) -> None:
        self.pen_up()
        ebb_motion.sendDisableMotors(self._port(), False)

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
        travel_x, travel_y = get_model(self._settings.model).travel_mm
        self._require().moveto(min(max(x, 0.0), travel_x), min(max(y, 0.0), travel_y))

    def jog(self, dx: float, dy: float) -> None:
        x, y = self.position()
        self.goto(x + dx, y + dy)

    def pen_up(self) -> None:
        self._require().penup()
        self._pen_is_down = False

    def pen_down(self) -> None:
        self._require().pendown()
        self._pen_is_down = True

    def set_pen_down_height(self, percent: int) -> None:
        if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= PEN_DOWN_MAX:
            raise ValueError(f"Pen-down height must be a whole number from 0 to {PEN_DOWN_MAX}.")
        ad = self._require()
        self._settings.pen_down = percent
        ad.options.pen_pos_down = percent
        ad.options.pen_pos_up = self._settings.pen_up
        ad.update()
        if self._pen_is_down:  # re-lower so the new height shows on the real pen
            ad.penup()
            ad.pendown()

    def trace(self, rect: tuple[float, float, float, float]) -> None:
        """Pen up: go around rect so the student sees where the drawing lands, then Home."""
        x0, y0, x1, y1 = rect
        self.pen_up()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)):
            self.goto(x, y)
        self.goto(0.0, 0.0)

    def test_mark(self, corner_x: float, corner_y: float) -> None:
        """A 10 mm line just inside the paper corner nearest Home, then back Home."""
        self.pen_up()
        self.goto(corner_x + 5, corner_y + 5)
        self._require().lineto(corner_x + 15, corner_y + 5)
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

    def _port(self):
        return self._require().plot_status.port
