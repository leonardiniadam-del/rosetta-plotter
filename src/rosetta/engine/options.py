"""Rosetta's plot settings, and how they map onto EMS pyaxidraw options."""
from dataclasses import dataclass

from rosetta.models import MODELS, PEN_TYPES, PEN_UP_SPEED


@dataclass
class PlotSettings:
    model: int  # EMS model number (rosetta.models.MODELS)
    penlift: int = 1  # EMS penlift: 1 default for model, 2 standard servo, 3 brushless
    pen_down: int = 30  # pen-down height, percent
    pen_type: str = "fineliner"  # key into rosetta.models.PEN_TYPES
    reordering: int = 2  # EMS: reorder and allow reversal
    hiding: bool = False  # EMS hidden-line removal (Advanced only)

    @property
    def pen_up(self) -> int:
        return min(100, max(60, self.pen_down + 20))


def apply_settings(ad, settings: PlotSettings) -> None:
    """Set EMS options. Call after ad.plot_setup() or ad.interactive()."""
    if settings.model not in MODELS:
        raise ValueError(f"Unknown AxiDraw model number: {settings.model}")
    if settings.pen_type not in PEN_TYPES:
        raise ValueError(f"Unknown pen type: {settings.pen_type}")
    options = ad.options
    options.model = settings.model
    options.penlift = settings.penlift
    options.pen_pos_down = settings.pen_down
    options.pen_pos_up = settings.pen_up
    options.speed_pendown = PEN_TYPES[settings.pen_type].speed_pendown
    options.speed_penup = PEN_UP_SPEED
    options.auto_rotate = False  # spec §4: never rotate; screen = paper
    options.reordering = settings.reordering
    options.hiding = settings.hiding


def make_axidraw():
    """A fresh EMS AxiDraw object. Imported lazily so non-engine code loads fast."""
    from pyaxidraw import axidraw

    return axidraw.AxiDraw()
