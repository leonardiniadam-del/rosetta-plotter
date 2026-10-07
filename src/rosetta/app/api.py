"""The page's way into Python (spec §6.5), documented in docs/bridge.md.

Every public method can be called from the page as `await window.pywebview.api.<name>(...)`. pywebview
runs each call on its own thread, so a slow one (an import, a plan, a move) never freezes the window.
Each replies {"ok": true, ...} or {"ok": false, "message": ..., "details": ...}.
pywebview exposes every public attribute it finds, so everything else here starts with an underscore.
"""
import dataclasses
import functools
import logging
import math

import rosetta
from rosetta.app import payloads
from rosetta.app.logs import diagnostics as diagnostics_text
from rosetta.app.machine import NOT_HOMED, Machine, MachineState
from rosetta.app.paper import CUSTOM, PAPER_SIZES, paper_dimensions
from rosetta.app.plotjob import FINISH_FIRST, PlotController
from rosetta.app.session import Session, pages_in
from rosetta.app.settings import MAX_MARGIN_MM, UNITS, PaperChoice, PenProfile, SettingsStore
from rosetta.compose import Material
from rosetta.engine.options import (
    ADVANCED_CHOICES, ADVANCED_LABELS, ADVANCED_RANGES, MIN_PEN_TRAVEL, PEN_DOWN_MAX, advanced_from_dict,
)
from rosetta.errors import ImportProblem, UserProblem
from rosetta.models import MODELS, PEN_TYPES, get_model

logger = logging.getLogger(__name__)

UNEXPECTED = "Something unexpected went wrong. Click Details, or Copy diagnostics to ask for help."
ARTWORK_TYPES = ("Drawings (*.svg;*.pdf;*.ai)",)
LARGEST_MODEL = 5  # SE/A1: before a plotter is known, only the paper limits the Pens panel
MAX_LABEL = 40


def _bridge(method):
    """Turn a method's result, or its exception, into the reply the page expects."""

    @functools.wraps(method)
    def call(self, *args):
        try:
            result = method(self, *args)
        except (UserProblem, ImportProblem) as problem:
            return {"ok": False, "message": str(problem), "details": getattr(problem, "details", "")}
        except Exception as error:  # a bug, or the plotter doing something odd: log it, say it plainly
            logger.exception("%s failed", method.__name__)
            return {"ok": False, "message": UNEXPECTED, "details": f"{type(error).__name__}: {error}"}
        return {"ok": True, **(result or {})}

    return call


def _finite(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Expected a number, got {value!r}")
    return float(value)


class Api:
    def __init__(self, store: SettingsStore, sink, machine: Machine | None = None,
                 runner_factory=None, log_path=None):
        self._store = store
        self._sink = sink
        self._machine = machine or Machine(store)
        self._machine.advanced = store.settings.advanced
        self._session = Session(self._saved_material(), store.settings.margin_mm)
        extra = {} if runner_factory is None else {"runner_factory": runner_factory}
        self._plot = PlotController(self._machine, self._session, sink, **extra)
        self._log_path = log_path
        self._window = None
        self._choose_files = None
        self._closing_allowed = False
        self._profile_key = None
        self._plotter_seen = None  # (identity, profile key) of the last plotter found

    # Wiring for main.py (underscored, so the page can't call it).

    def _attach_window(self, window, choose_files) -> None:
        self._window = window
        self._choose_files = choose_files

    def _files_dropped(self, paths: list[str]) -> None:
        self._sink.emit("files_dropped", {"paths": list(paths)})

    def _on_closing(self) -> bool:
        """The window's closing event, on the window's own thread; True lets it close. Mid-plot the page
        is asked to confirm first (spec §10), and its Quit button calls quit_confirmed(), which stops
        everything before it closes the window, so nothing here has to wait."""
        if self._closing_allowed:
            return True
        if not self._plot.busy():
            self._plot.shutdown()
            self._machine.shutdown()
            return True
        self._sink.emit("close_requested", {})
        return False

    # App.

    @_bridge
    def app_start(self):
        """Everything the page needs for its first screen."""
        settings = self._store.settings
        return {
            "version": rosetta.__version__,
            "settings": {
                "units": settings.units,
                "margin_mm": settings.margin_mm,
                "paper": dataclasses.asdict(settings.paper),
                "advanced": dataclasses.asdict(settings.advanced),
            },
            "models": [
                {"number": model.number, "name": model.name, "travel": list(model.travel_mm)}
                for model in MODELS.values()
            ],
            "pen_types": [
                {"key": pen.key, "label": pen.label, "speed": pen.speed_pendown} for pen in PEN_TYPES.values()
            ],
            "papers": [
                {"key": paper.key, "label": paper.label, "short_mm": paper.short_mm, "long_mm": paper.long_mm}
                for paper in PAPER_SIZES.values()
            ],
            "advanced_options": {
                "labels": ADVANCED_LABELS,
                "ranges": {name: list(bounds) for name, bounds in ADVANCED_RANGES.items()},
                "choices": {name: list(values) for name, values in ADVANCED_CHOICES.items()},
            },
            "pen_down_max": PEN_DOWN_MAX,
            "machine": self._machine.status(),
            "material": self._material(),
            "plot": self._plot.status(),
        }

    @_bridge
    def set_units(self, units):
        if units not in UNITS:
            raise ValueError(f"Unknown units: {units!r}")
        with self._store.change() as settings:
            settings.units = units

    @_bridge
    def set_advanced(self, values):
        """Change some Advanced options; the others keep their values (the page sends only what changed)."""
        try:
            values = dict(values)
            advanced_from_dict(values)  # checks each value given
        except (ValueError, TypeError) as problem:  # typed by the student, so the message is for them
            raise UserProblem(str(problem)) from problem
        with self._store.change() as settings:
            advanced = dataclasses.replace(settings.advanced, **values)
            pen_down = self._machine.pen_down
            # Checked only when pen-up itself changes: a clash left from another plotter's pen-down is set
            # aside when connecting (Machine._settings), and mustn't block unrelated options.
            if "pen_up" in values and advanced.pen_up is not None and advanced.pen_up - pen_down < MIN_PEN_TRAVEL:
                raise UserProblem(
                    f"Pen-up height must be at least {MIN_PEN_TRAVEL} above the pen-down height ({pen_down})."
                )
            settings.advanced = advanced
            self._machine.advanced = advanced
        self._plot.invalidate()
        return {"advanced": dataclasses.asdict(advanced)}

    @_bridge
    def diagnostics(self):
        machine = self._machine.status()
        extra = {
            "Plotter": f"{machine['model_name'] or 'unknown model'} ({machine['state']}), "
                       f"firmware {machine['firmware'] or 'unknown'}",
            "Plot": self._plot.status()["state"],
        }
        return {"text": diagnostics_text(self._log_path, extra)}

    @_bridge
    def quit_confirmed(self):
        """The student confirmed closing mid-plot: pause the plot (pen up), let go of the plotter, then
        close the window. This runs on a bridge thread, so the wait doesn't freeze the window."""
        self._plot.shutdown()
        self._machine.shutdown()
        self._closing_allowed = True
        if self._window is not None:
            self._window.destroy()

    # Step 1 and Re-home: the plotter.

    @_bridge
    def plotter_scan(self):
        """Look for the plotter (the page calls this every 2 s while none is connected)."""
        self._machine.scan()
        self._load_profile()
        return {"machine": self._machine.status()}

    @_bridge
    def plotter_identify(self, model, penlift, label=""):
        if model not in MODELS or penlift not in (1, 2, 3) or not isinstance(label, str) or len(label) > MAX_LABEL:
            raise ValueError(f"Bad plotter identity: {model!r}, {penlift!r}, {label!r}")
        self._machine.identify(model, penlift, label)
        self._load_profile()
        return {"machine": self._machine.status()}

    @_bridge
    def plotter_motors_off(self):
        return {"machine": self._machine.motors_off()}

    @_bridge
    def plotter_set_home(self):
        return {"machine": self._machine.set_home()}

    @_bridge
    def plotter_jog(self, dx, dy):
        return {"machine": self._machine.jog(_finite(dx), _finite(dy))}

    @_bridge
    def plotter_goto(self, x, y):
        return {"machine": self._machine.goto(_finite(x), _finite(y))}

    @_bridge
    def plotter_pen(self, down):
        return {"machine": self._machine.pen(bool(down))}

    @_bridge
    def plotter_stop(self):
        self._machine.request_stop()

    @_bridge
    def plotter_test_mark(self):
        material = self._session.material
        return {"machine": self._machine.test_mark(material.x, material.y)}

    @_bridge
    def pen_set(self, pen_down, pen_type):
        status = self._machine.set_pen(pen_down, pen_type)
        key = self._machine.profile_key()
        if key:
            with self._store.change() as settings:
                settings.profiles[key] = PenProfile(pen_down, pen_type)
        self._plot.invalidate()
        return {"machine": status}

    # Step 2: the paper.

    @_bridge
    def material_set(self, size, orientation, custom_width_mm=None, custom_height_mm=None, x=0.0, y=0.0):
        width, height = paper_dimensions(size, orientation, custom_width_mm, custom_height_mm)
        x, y = _finite(x), _finite(y)
        if x < 0 or y < 0:
            raise UserProblem("Place the paper's corner at the Home corner or farther from it.")
        self._session.material = Material(x, y, width, height)
        custom = size == CUSTOM
        with self._store.change() as settings:
            settings.paper = PaperChoice(size, orientation, width if custom else None, height if custom else None)
        self._plot.invalidate()
        return {"material": self._material()}

    @_bridge
    def material_mark_corner(self):
        """"Mark this corner": the paper's corner nearest Home is where the pen is now (spec §5, step 2)."""
        if self._machine.state is not MachineState.READY:
            raise UserProblem(NOT_HOMED)
        x, y = self._machine.position
        self._session.material = dataclasses.replace(self._session.material, x=x, y=y)
        self._plot.invalidate()
        return {"material": self._material()}

    @_bridge
    def set_margin(self, margin_mm):
        margin = _finite(margin_mm)
        if not 0 <= margin <= MAX_MARGIN_MM:
            raise UserProblem(f"The margin must be from 0 to {MAX_MARGIN_MM:g} mm.")
        self._session.margin_mm = margin
        with self._store.change() as settings:
            settings.margin_mm = margin
        return {"margin_mm": margin}

    # Step 3: artwork.

    @_bridge
    def artwork_choose(self):
        """Windows' Open dialog. The page then asks for page counts and imports each chosen file."""
        if self._choose_files is None:
            raise UserProblem("The file picker isn't available.")
        return {"paths": [str(path) for path in (self._choose_files() or [])]}

    @_bridge
    def artwork_pages(self, path):
        return {"pages": pages_in(path)}

    @_bridge
    def artwork_import(self, path, page=0):
        piece, shrunk = self._session.add(path, int(page))
        self._plot.invalidate()
        return {"piece": payloads.piece_payload(piece), "shrunk": shrunk}

    @_bridge
    def piece_place(self, piece_id, x, y, scale, rotation):
        piece = self._session.place(piece_id, x, y, scale, rotation)
        self._plot.invalidate()
        return {"placement": payloads.placement_payload(piece.placement)}

    @_bridge
    def piece_duplicate(self, piece_id):
        piece = self._session.duplicate(piece_id)
        self._plot.invalidate()
        return {"piece": payloads.piece_payload(piece)}

    @_bridge
    def piece_delete(self, piece_id):
        self._session.remove(piece_id)
        self._plot.invalidate()

    @_bridge
    def set_skip_white(self, skip):
        self._session.skip_white = bool(skip)
        self._plot.invalidate()
        return {"skip_white": self._session.skip_white}

    @_bridge
    def job_colors(self):
        """The pens the drawing needs, in plot order (the Pens panel)."""
        identity = self._machine.identity
        model = get_model(identity.model if identity else LARGEST_MODEL)
        return payloads.job_payload(self._session.compose(model))

    @_bridge
    def new_plot(self):
        """Start again with empty paper (the Done screen's New plot)."""
        if self._plot.busy():
            raise UserProblem(FINISH_FIRST)
        self._session.clear()
        self._plot.invalidate()

    # Step 5: the plot.

    @_bridge
    def plot_prepare(self):
        return {"summary": self._plot.prepare()}

    @_bridge
    def plot_trace(self):
        return {"machine": self._plot.trace()}

    @_bridge
    def plot_start(self):
        self._plot.start()
        return self._plot_reply()

    @_bridge
    def plot_continue(self):
        self._plot.continue_pen()
        return self._plot_reply()

    @_bridge
    def plot_pause(self):
        self._plot.pause()
        return self._plot_reply()

    @_bridge
    def plot_resume(self):
        self._plot.resume()
        return self._plot_reply()

    @_bridge
    def plot_home(self):
        self._plot.home()
        return self._plot_reply()

    @_bridge
    def plot_cancel(self):
        self._plot.cancel()
        return self._plot_reply()

    @_bridge
    def plot_reconnect(self):
        self._plot.reconnect()
        return self._plot_reply()

    @_bridge
    def plot_rehomed(self):
        self._plot.rehomed()
        return self._plot_reply()

    @_bridge
    def plot_retry(self):
        self._plot.retry()
        return self._plot_reply()

    @_bridge
    def plot_status(self):
        return self._plot_reply()

    # Inside.

    def _plot_reply(self) -> dict:
        return {"plot": self._plot.status(), "machine": self._machine.status()}

    def _material(self) -> dict:
        identity = self._machine.identity
        return payloads.material_payload(self._session.material, get_model(identity.model) if identity else None)

    def _saved_material(self) -> Material:
        paper = self._store.settings.paper
        try:
            width, height = paper_dimensions(
                paper.size, paper.orientation, paper.custom_width_mm, paper.custom_height_mm
            )
        except (UserProblem, ValueError):
            width, height = paper_dimensions("letter", "landscape")
        return Material(0.0, 0.0, width, height)

    def _load_profile(self) -> None:
        """When a different plotter shows up, start from the pen settings it was last used with. A plot
        prepared for another plotter (or under another name) is out of date: its reach and pen differ."""
        identity, key = self._machine.identity, self._machine.profile_key()
        if identity is not None and (identity, key) != self._plotter_seen:
            self._plotter_seen = (identity, key)
            self._plot.invalidate()
        if key == self._profile_key:
            return
        self._profile_key = key
        profile = self._store.settings.profiles.get(key) if key else None
        if profile is not None:
            try:
                self._machine.set_pen(profile.pen_down, profile.pen_type)
            except (UserProblem, ValueError):
                logger.info("Couldn't use the saved pen settings for %s", key, exc_info=True)
