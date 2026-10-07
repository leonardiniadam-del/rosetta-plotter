"""The one owner of the plotter connection (spec §6.1).

Steps 1-4 move the plotter through the EMS interactive context. A plot run takes the USB port with
release_for_plot() and gives it back with after_plot(). Only one request uses the plotter at a time:
a second one gets a "still busy" message instead of waiting, except request_stop(), which works any time.
"""
import contextlib
import logging
import threading
import time
from enum import Enum

from rosetta.app.settings import StoredIdentity
from rosetta.engine.identity import Identity, encode_nickname
from rosetta.engine.options import MIN_PEN_TRAVEL, PEN_DOWN_MAX, Advanced, PlotSettings
from rosetta.engine.plotter import IdentityWrite, Plotter, PlotterStopped
from rosetta.errors import UserProblem
from rosetta.models import PEN_TYPES, get_model

logger = logging.getLogger(__name__)

REBOOT_WAIT_S = 3.0  # the board restarts after its name is written
RECONNECT_TRIES = 10
RECONNECT_PAUSE_S = 1.0
SHUTDOWN_WAIT_S = 10.0

BUSY = "The plotter is still busy. Wait for it to finish, then try again."
NOT_CONNECTED = "No plotter is connected. Plug in the USB cable and the power adapter."
NEEDS_MODEL = "Choose which AxiDraw this is first."
NOT_HOMED = ("Slide the pen to the corner next to the HOME label and the USB port, "
             "then click It's in the corner.")
PLOTTING = "The plotter is plotting. Pause or stop the plot first."
STOPPED_MOVING = ("The plotter stopped before the move finished. Slide the pen Home, "
                  "then click It's in the corner.")
NO_POWER = "The power adapter isn't plugged in. The pen can't move without it."
NAME_NOT_SAVED = "The plotter didn't accept its new name. Check the USB cable and try again."
NO_RETURN = ("The plotter didn't come back after saving its name. Unplug the USB cable, "
             "plug it back in, and try again.")


class MachineState(Enum):
    NO_PLOTTER = "no_plotter"
    NEEDS_MODEL = "needs_model"  # connected, but which AxiDraw it is isn't known
    NOT_HOMED = "not_homed"  # connected and known, but where the pen is isn't
    READY = "ready"  # homed: the pen's position is known
    PLOTTING = "plotting"  # a plot run has the USB port


_REFUSALS = {
    MachineState.NO_PLOTTER: NOT_CONNECTED,
    MachineState.NEEDS_MODEL: NEEDS_MODEL,
    MachineState.NOT_HOMED: NOT_HOMED,
    MachineState.READY: BUSY,
    MachineState.PLOTTING: PLOTTING,
}
_CONNECTED = (MachineState.NEEDS_MODEL, MachineState.NOT_HOMED, MachineState.READY)
_KNOWN = (MachineState.NOT_HOMED, MachineState.READY)


class Machine:
    def __init__(self, store, plotter_factory=Plotter, sleep=time.sleep):
        self._store = store  # SettingsStore: models remembered for old firmware
        self._new_plotter = plotter_factory
        self._sleep = sleep
        self._lock = threading.Lock()
        self._plotter: Plotter | None = None
        self.state = MachineState.NO_PLOTTER
        self.identity: Identity | None = None
        self.firmware = ""
        self.nickname: str | None = None
        self.port: str | None = None
        self.power_ok = False
        self.old_firmware = False
        self.position = (0.0, 0.0)
        self.pen_down = 30
        self.pen_type = "fineliner"
        self.advanced = Advanced()

    # What the page sees.

    def status(self) -> dict:
        identity = self.identity
        return {
            "state": self.state.value,
            "firmware": self.firmware,
            "power_ok": self.power_ok,
            "model": identity.model if identity else None,
            "model_name": get_model(identity.model).name if identity else None,
            "penlift": identity.penlift if identity else None,
            "label": identity.label if identity else None,
            "nickname": self.nickname,
            "old_firmware": self.old_firmware,
            "position": list(self.position) if self.state is MachineState.READY else None,
            "pen_down": self.pen_down,
            "pen_type": self.pen_type,
        }

    def plot_settings(self) -> PlotSettings:
        if self.identity is None:
            raise UserProblem(NOT_CONNECTED)
        return self._settings()

    def profile_key(self) -> str | None:
        """Where this plotter's pen settings are kept: its nickname, or its port on old firmware."""
        if self.identity is None:
            return None
        if self.old_firmware:
            return f"port:{self.port}" if self.port else None
        return self.nickname

    # Step 1: connect, identify, Home.

    def scan(self) -> dict:
        """Look for the plotter, or check the connected one is still there. Never raises."""
        if not self._lock.acquire(blocking=False):
            return self.status()  # something is using it, so it's plainly there
        try:
            if self.state is MachineState.PLOTTING:
                return self.status()
            if self._plotter is not None and not self._still_there():
                self._drop()
            if self._plotter is None:
                self._connect_and_identify()
            return self.status()
        finally:
            self._lock.release()

    def identify(self, model: int, penlift: int, label: str) -> dict:
        """Store which AxiDraw this is (spec §8): in its nickname, or on this laptop if the firmware is
        too old. Returns the status after reconnecting; its nickname echoes what the plotter stored."""
        identity = Identity(model, penlift, label)
        encode_nickname(identity)  # ValueError for an unknown model or pen lift, before anything is written
        with self._using(*_CONNECTED) as plotter:
            port = self.port
            result = plotter.write_identity(identity)  # always ends the connection
            self._plotter = None
            if result is IdentityWrite.WRITTEN:
                self._sleep(REBOOT_WAIT_S)
            elif result is not IdentityWrite.FAILED and port:
                self._store.settings.old_firmware[port] = StoredIdentity(model, penlift, label)
                self._store.save()
            else:
                self._forget()
                raise UserProblem(NAME_NOT_SAVED)
            for _attempt in range(RECONNECT_TRIES):
                self._connect_and_identify()
                if self._plotter is not None:
                    return self.status()
                self._sleep(RECONNECT_PAUSE_S)
            raise UserProblem(NO_RETURN)

    def motors_off(self) -> dict:
        """Let go of the carriage so the student can slide the pen Home (the start of Home and Re-home)."""
        with self._using(*_KNOWN) as plotter:
            plotter.motors_off()
            self.state = MachineState.NOT_HOMED
        return self.status()

    def set_home(self) -> dict:
        """The student says the pen is in the Home corner: from now on it's (0, 0)."""
        with self._using(*_KNOWN) as plotter:
            self._check_power(plotter)
            try:
                plotter.set_home()
            except RuntimeError as lost:  # Plotter.set_home couldn't reconnect
                self._drop()
                raise UserProblem(NOT_CONNECTED, details=str(lost)) from lost
            self.position = (0.0, 0.0)
            self.state = MachineState.READY
        return self.status()

    # Step 4: the pen.

    def set_pen(self, pen_down: int, pen_type: str) -> dict:
        """The Pen step's height slider and pen type. A connected pen moves to the new height at once."""
        if isinstance(pen_down, bool) or not isinstance(pen_down, int) or not 0 <= pen_down <= PEN_DOWN_MAX:
            raise ValueError(f"Pen-down height must be a whole number from 0 to {PEN_DOWN_MAX}.")
        if pen_type not in PEN_TYPES:
            raise ValueError(f"Unknown pen type: {pen_type!r}")
        pen_up = self.advanced.pen_up
        if pen_up is not None and pen_up - pen_down < MIN_PEN_TRAVEL:
            raise UserProblem(
                f"The pen-up height under Advanced ({pen_up}) must be at least {MIN_PEN_TRAVEL} above "
                "the pen-down height."
            )
        if self._plotter is not None and self.state in _KNOWN:
            with self._using(*_KNOWN) as plotter:
                plotter.set_pen_down_height(pen_down)
        self.pen_down, self.pen_type = pen_down, pen_type
        return self.status()

    # Any time.

    def request_stop(self) -> None:
        """Stop a move in progress at its next step, pen up. Safe from any thread, busy or not."""
        plotter = self._plotter
        if plotter is not None:
            plotter.request_pause()

    def shutdown(self) -> None:
        """The app is closing: stop any move, lift the pen and let go of the USB port."""
        self.request_stop()
        if self._lock.acquire(timeout=SHUTDOWN_WAIT_S):
            try:
                self._drop()
            finally:
                self._lock.release()

    # Inside.

    @contextlib.contextmanager
    def _using(self, *allowed: MachineState):
        """One request at a time, in a state that allows it. A move that stops partway (Stop, the pause
        button, a pulled cable) leaves the pen's position unknown."""
        if not self._lock.acquire(blocking=False):
            raise UserProblem(BUSY)
        try:
            if self.state not in allowed:
                raise UserProblem(_REFUSALS[self.state])
            yield self._plotter
        except PlotterStopped as stopped:
            self._after_stop()
            raise UserProblem(STOPPED_MOVING, details=str(stopped)) from stopped
        finally:
            self._lock.release()

    def _after_stop(self) -> None:
        """EMS ignores moves after a stop, so start a fresh connection; it frees the carriage for re-homing."""
        self._drop()
        self._connect_and_identify()

    def _check_power(self, plotter: Plotter) -> None:
        self.power_ok = plotter.power_ok()
        if not self.power_ok:
            raise UserProblem(NO_POWER)

    def _settings(self) -> PlotSettings:
        identity = self.identity
        return PlotSettings(
            model=identity.model if identity else 1,
            penlift=identity.penlift if identity else 1,
            pen_down=self.pen_down,
            pen_type=self.pen_type,
            advanced=self.advanced,
        )

    def _still_there(self) -> bool:
        """plotink answers an empty firmware version once the USB cable has been pulled."""
        try:
            if not self._plotter.firmware():
                return False
            self.power_ok = self._plotter.power_ok()
            return True
        except Exception:
            logger.info("The plotter stopped answering", exc_info=True)
            return False

    def _connect_and_identify(self) -> None:
        """Open the plotter, learn which it is, and free its carriage. NO_PLOTTER if it isn't there."""
        plotter = self._new_plotter()
        if not plotter.connect(self._settings()):
            self._forget()
            return
        try:
            self.firmware = plotter.firmware()
            self.power_ok = plotter.power_ok()
            self.port = plotter.port_name()
            self.nickname = plotter.nickname()
            identity = plotter.read_identity()
            self.old_firmware = False
            stored = self._store.settings.old_firmware.get(self.port) if self.port else None
            if identity is None and stored is not None:
                identity = Identity(stored.model, stored.penlift, stored.label)
                self.old_firmware = True
            self.identity = identity
            if identity is not None:
                plotter.disconnect()  # reconnect with this model's reach, so moves stay inside it
                if not plotter.connect(self._settings()):
                    self._forget()
                    return
            plotter.motors_off()  # connecting holds the carriage; the student is about to slide it Home
        except PlotterStopped:
            plotter.disconnect()
            self._forget()
            return
        self._plotter = plotter
        self.state = MachineState.NOT_HOMED if identity is not None else MachineState.NEEDS_MODEL

    def _drop(self) -> None:
        plotter, self._plotter = self._plotter, None
        if plotter is not None:
            try:
                plotter.disconnect()
            except Exception:
                logger.info("Couldn't close the plotter's connection", exc_info=True)
        self._forget()

    def _forget(self) -> None:
        self.state = MachineState.NO_PLOTTER
        self.identity = None
        self.firmware = ""
        self.nickname = None
        self.port = None
        self.power_ok = False
        self.old_firmware = False
