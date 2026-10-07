"""Rosetta's plot settings, and how they map onto EMS pyaxidraw options."""
import dataclasses
import logging
import os
import sys
from dataclasses import dataclass, field

from rosetta.models import MODELS, PEN_TYPES, PEN_UP_SPEED

PEN_DOWN_MAX = 80  # keeps at least 20% of servo travel between pen down and pen up
MIN_PEN_TRAVEL = 10  # an Advanced pen-up height must be at least this far above pen-down


@dataclass(frozen=True)
class Advanced:
    """Engine options a student only sees under "Advanced" (spec §5). None means Rosetta decides."""

    pen_up: int | None = None  # percent; None = max(60, pen-down + 20), capped at 100
    speed_pendown: int | None = None  # percent of maximum; None = the pen type's speed
    speed_penup: int = PEN_UP_SPEED
    accel: int = 75
    pen_rate_raise: int = 75
    pen_rate_lower: int = 50
    pen_delay_up: int = 0  # ms
    pen_delay_down: int = 0  # ms
    reordering: int = 2  # 0 join nearby ends only, 1 reorder, 2 reorder and reverse, 4 keep file order
    hiding: bool = False  # hidden-line removal
    resolution: int = 1  # 1 fine, 2 coarse (faster)


ADVANCED_LABELS = {
    "pen_up": "Pen-up height",
    "speed_pendown": "Pen-down speed",
    "speed_penup": "Pen-up speed",
    "accel": "Acceleration",
    "pen_rate_raise": "Pen raising speed",
    "pen_rate_lower": "Pen lowering speed",
    "pen_delay_up": "Delay after raising the pen",
    "pen_delay_down": "Delay after lowering the pen",
    "reordering": "Path order",
    "hiding": "Hidden-line removal",
    "resolution": "Resolution",
}
ADVANCED_RANGES = {
    "pen_up": (0, 100),
    "speed_pendown": (1, 100),
    "speed_penup": (1, 100),
    "accel": (1, 100),
    "pen_rate_raise": (1, 100),
    "pen_rate_lower": (1, 100),
    "pen_delay_up": (0, 1000),
    "pen_delay_down": (0, 1000),
}
ADVANCED_CHOICES = {"reordering": (0, 1, 2, 4), "resolution": (1, 2)}
_AUTOMATIC = ("pen_up", "speed_pendown")  # None means "Rosetta decides"


def advanced_from_dict(values: dict) -> Advanced:
    """Advanced options from the page or settings.json. ValueError with a plain message if one is wrong."""
    for name, value in values.items():
        label = ADVANCED_LABELS.get(name)
        if label is None:
            raise ValueError(f"Unknown advanced option: {name}")
        if name == "hiding":
            if not isinstance(value, bool):
                raise ValueError(f"{label} must be on or off.")
            continue
        if value is None and name in _AUTOMATIC:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} must be a whole number.")
        if name in ADVANCED_CHOICES:
            choices = ADVANCED_CHOICES[name]
            if value not in choices:
                raise ValueError(f"{label} must be one of {', '.join(str(choice) for choice in choices)}.")
        else:
            low, high = ADVANCED_RANGES[name]
            if not low <= value <= high:
                raise ValueError(f"{label} must be from {low} to {high}.")
    return Advanced(**values)


@dataclass
class PlotSettings:
    model: int  # EMS model number (rosetta.models.MODELS)
    penlift: int = 1  # EMS penlift: 1 default for model, 2 standard servo, 3 brushless
    pen_down: int = 30  # pen-down height, percent
    pen_type: str = "fineliner"  # key into rosetta.models.PEN_TYPES
    advanced: Advanced = field(default_factory=Advanced)

    @property
    def pen_up(self) -> int:
        if self.advanced.pen_up is not None:
            return self.advanced.pen_up
        return min(100, max(60, self.pen_down + 20))


def apply_settings(ad, settings: PlotSettings) -> None:
    """Set EMS options. Call after ad.plot_setup() or ad.interactive()."""
    if settings.model not in MODELS:
        raise ValueError(f"Unknown AxiDraw model number: {settings.model}")
    if settings.pen_type not in PEN_TYPES:
        raise ValueError(f"Unknown pen type: {settings.pen_type}")
    if settings.penlift not in (1, 2, 3):
        raise ValueError(f"Unknown pen lift: {settings.penlift!r} (use 1, 2 or 3)")
    pen_down = settings.pen_down
    whole_number = isinstance(pen_down, int) and not isinstance(pen_down, bool)
    if not whole_number or not 0 <= pen_down <= PEN_DOWN_MAX:
        raise ValueError(f"Pen-down height must be a whole number, 0 to {PEN_DOWN_MAX}: {pen_down!r}")
    advanced = advanced_from_dict(dataclasses.asdict(settings.advanced))
    if advanced.pen_up is not None and advanced.pen_up - pen_down < MIN_PEN_TRAVEL:
        raise ValueError(f"Pen-up height must be at least {MIN_PEN_TRAVEL} above the pen-down height.")
    options = ad.options
    options.model = settings.model
    options.penlift = settings.penlift
    options.pen_pos_down = pen_down
    options.pen_pos_up = settings.pen_up
    options.speed_pendown = advanced.speed_pendown or PEN_TYPES[settings.pen_type].speed_pendown
    options.speed_penup = advanced.speed_penup
    options.accel = advanced.accel
    options.pen_rate_raise = advanced.pen_rate_raise
    options.pen_rate_lower = advanced.pen_rate_lower
    options.pen_delay_up = advanced.pen_delay_up
    options.pen_delay_down = advanced.pen_delay_down
    options.auto_rotate = False  # spec §4: never rotate; screen = paper
    options.reordering = advanced.reordering
    options.hiding = advanced.hiding
    options.resolution = advanced.resolution


def ensure_std_streams() -> None:
    """Windowed (no-console) builds have sys.stdout/sys.stderr = None, and EMS writes to them."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def _log_ems_message(text) -> None:
    """EMS reports pauses, warnings and the like through a callback; Rosetta keeps them in the log."""
    logging.getLogger("rosetta.ems").info(text)


def make_axidraw():
    """A fresh EMS AxiDraw object. Imported lazily so non-engine code loads fast."""
    ensure_std_streams()
    from pyaxidraw import axidraw

    return axidraw.AxiDraw(user_message_fun=_log_ems_message)
