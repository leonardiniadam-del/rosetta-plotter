"""Per-laptop settings in %APPDATA%\\RosettaPlotter\\settings.json (spec §6.4).

Loading never fails: a missing file gives the defaults, a damaged one is set aside as
settings.json.bad, and a single bad value falls back to its own default. Change them with
SettingsStore.change(), which saves them too.
"""
import contextlib
import dataclasses
import json
import logging
import math
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from rosetta.app.paper import CUSTOM, DEFAULT_ORIENTATION, MAX_CUSTOM_MM, ORIENTATIONS, PAPER_SIZES
from rosetta.compose import DEFAULT_MARGIN_MM
from rosetta.engine.options import PEN_DOWN_MAX, Advanced, advanced_from_dict
from rosetta.models import MODELS, PEN_TYPES

logger = logging.getLogger(__name__)

APP_FOLDER = "RosettaPlotter"
SETTINGS_VERSION = 1
UNITS = ("in", "mm", "cm")
MAX_MARGIN_MM = 50.0
# How the plate is turned to match the plotter as the student faces it (orientation spec §1):
# the screen corner HOME is in, then whether machine X runs across (h) or up/down (v).
VIEW_ORIENTATIONS = ("nw-h", "nw-v", "ne-h", "ne-v", "se-h", "se-v", "sw-h", "sw-v")
DEFAULT_VIEW_ORIENTATION = "nw-h"


def app_folder() -> Path:
    """%APPDATA%\\RosettaPlotter (under the home folder if APPDATA isn't set)."""
    return Path(os.environ.get("APPDATA") or Path.home()) / APP_FOLDER


@dataclass
class PaperChoice:
    size: str = "letter"
    orientation: str = DEFAULT_ORIENTATION
    custom_width_mm: float | None = None
    custom_height_mm: float | None = None


@dataclass
class PenProfile:
    """What a plotter was last used with, so the next session on it starts there."""

    pen_down: int = 30
    pen_type: str = "fineliner"


@dataclass
class StoredIdentity:
    """A plotter whose firmware is too old to hold its model, remembered on this laptop (spec §8)."""

    model: int
    penlift: int = 1
    label: str = ""


@dataclass
class Settings:
    units: str = "in"
    paper: PaperChoice = field(default_factory=PaperChoice)
    margin_mm: float = DEFAULT_MARGIN_MM
    advanced: Advanced = field(default_factory=Advanced)
    profiles: dict[str, PenProfile] = field(default_factory=dict)  # keyed by Machine.profile_key()
    old_firmware: dict[str, StoredIdentity] = field(default_factory=dict)  # keyed by serial port
    orientation: str = DEFAULT_VIEW_ORIENTATION  # the last one used on this laptop
    orientations: dict[str, str] = field(default_factory=dict)  # keyed by Machine.profile_key()


class SettingsStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()  # bridge calls run on threads of their own
        self.settings = self._load()

    @contextlib.contextmanager
    def change(self):
        """Change the settings, then save them, one change at a time:
        `with store.change() as settings: settings.units = "mm"`. Nothing is saved if the change fails."""
        with self._lock:
            yield self.settings
            self.save()

    def save(self) -> None:
        """Write atomically. A failure is logged, not raised: losing a preference mustn't stop a plot."""
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                scratch = self.path.with_name(self.path.name + ".tmp")
                scratch.write_text(json.dumps(_to_json(self.settings), indent=2), encoding="utf-8")
                os.replace(scratch, self.path)
            except OSError:
                logger.warning("Couldn't save settings to %s", self.path, exc_info=True)

    def _load(self) -> Settings:
        try:
            text = self.path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return Settings()
        except OSError:
            logger.warning("Couldn't read %s; using the default settings", self.path, exc_info=True)
            return Settings()
        except UnicodeDecodeError:
            self._set_aside()
            return Settings()
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            self._set_aside()
            return Settings()
        return _from_json(data)

    def _set_aside(self) -> None:
        logger.warning("%s is damaged; keeping it as settings.json.bad and using the defaults", self.path)
        try:
            os.replace(self.path, self.path.with_name(self.path.name + ".bad"))
        except OSError:
            logger.warning("Couldn't set %s aside", self.path, exc_info=True)


def _to_json(settings: Settings) -> dict:
    return {"version": SETTINGS_VERSION, **dataclasses.asdict(settings)}


def _from_json(data: dict) -> Settings:
    defaults = Settings()
    return Settings(
        units=_choice(data.get("units"), UNITS, defaults.units),
        paper=_paper(data.get("paper")),
        margin_mm=_number(data.get("margin_mm"), 0.0, MAX_MARGIN_MM, defaults.margin_mm),
        advanced=_advanced(data.get("advanced")),
        profiles=_profiles(data.get("profiles")),
        old_firmware=_identities(data.get("old_firmware")),
        orientation=_choice(data.get("orientation"), VIEW_ORIENTATIONS, defaults.orientation),
        orientations=_orientations(data.get("orientations")),
    )


def _choice(value, choices, default):
    return value if isinstance(value, str) and value in choices else default


def _number(value, low, high, default):
    usable = (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and low <= value <= high
    )
    return float(value) if usable else default


def _whole(value, low, high, default):
    usable = isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    return value if usable else default


def _paper(data) -> PaperChoice:
    default = PaperChoice()
    if not isinstance(data, dict):
        return default
    size = _choice(data.get("size"), (*PAPER_SIZES, CUSTOM), default.size)
    width = _number(data.get("custom_width_mm"), 0.1, MAX_CUSTOM_MM, None)
    height = _number(data.get("custom_height_mm"), 0.1, MAX_CUSTOM_MM, None)
    if size == CUSTOM and (width is None or height is None):
        size = default.size
    orientation = _choice(data.get("orientation"), ORIENTATIONS, default.orientation)
    return PaperChoice(size, orientation, width, height)


def _advanced(data) -> Advanced:
    if not isinstance(data, dict):
        return Advanced()
    kept = {}
    for name, value in data.items():
        try:
            advanced_from_dict({name: value})
        except (ValueError, TypeError):
            logger.warning("Ignoring the saved advanced option %s=%r", name, value)
            continue
        kept[name] = value
    return Advanced(**kept)


def _profiles(data) -> dict[str, PenProfile]:
    if not isinstance(data, dict):
        return {}
    default = PenProfile()
    return {
        key: PenProfile(
            _whole(value.get("pen_down"), 0, PEN_DOWN_MAX, default.pen_down),
            _choice(value.get("pen_type"), tuple(PEN_TYPES), default.pen_type),
        )
        for key, value in data.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def _orientations(data) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    return {key: value for key, value in data.items() if isinstance(key, str) and value in VIEW_ORIENTATIONS}


def _identities(data) -> dict[str, StoredIdentity]:
    if not isinstance(data, dict):
        return {}
    kept = {}
    for port, value in data.items():
        if not (isinstance(port, str) and isinstance(value, dict)):
            continue
        model = _whole(value.get("model"), 1, max(MODELS), None)
        penlift = _whole(value.get("penlift", 1), 1, 3, None)
        label = value.get("label", "")
        if model in MODELS and penlift is not None and isinstance(label, str):
            kept[port] = StoredIdentity(model, penlift, label)
    return kept
