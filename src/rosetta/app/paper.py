"""Paper sizes the student picks from in the Material step (spec §5, step 2).

Width runs along the rail (left-right on screen), height toward the student. Every AxiDraw reaches
farther along its rail than toward the student, so landscape is the default.
"""
import math
from dataclasses import dataclass

from rosetta.errors import UserProblem
from rosetta.units import MM_PER_INCH

ORIENTATIONS = ("landscape", "portrait")
DEFAULT_ORIENTATION = "landscape"
CUSTOM = "custom"
MAX_CUSTOM_MM = 2000.0  # bigger than any AxiDraw's reach; anything larger is a typo


@dataclass(frozen=True)
class PaperSize:
    key: str
    label: str
    short_mm: float
    long_mm: float


PAPER_SIZES = {
    paper.key: paper
    for paper in (
        PaperSize("letter", "Letter", 8.5 * MM_PER_INCH, 11 * MM_PER_INCH),
        PaperSize("legal", "Legal", 8.5 * MM_PER_INCH, 14 * MM_PER_INCH),
        PaperSize("tabloid", "Tabloid 11×17", 11 * MM_PER_INCH, 17 * MM_PER_INCH),
        PaperSize("a4", "A4", 210.0, 297.0),
        PaperSize("a3", "A3", 297.0, 420.0),
        PaperSize("a2", "A2", 420.0, 594.0),
        PaperSize("a1", "A1", 594.0, 841.0),
    )
}


def paper_dimensions(
    size: str, orientation: str, custom_width_mm=None, custom_height_mm=None
) -> tuple[float, float]:
    """(width, height) in mm on the machine. Custom sizes are taken exactly as typed (the page swaps
    its two fields when the student flips the orientation)."""
    if orientation not in ORIENTATIONS:
        raise ValueError(f"Unknown orientation: {orientation!r}")
    if size == CUSTOM:
        for value in (custom_width_mm, custom_height_mm):
            if not _usable_length(value):
                raise UserProblem(f"Paper width and height must be between 0 and {MAX_CUSTOM_MM:g} mm.")
        return float(custom_width_mm), float(custom_height_mm)
    paper = PAPER_SIZES.get(size)
    if paper is None:
        raise ValueError(f"Unknown paper size: {size!r}")
    if orientation == "landscape":
        return paper.long_mm, paper.short_mm
    return paper.short_mm, paper.long_mm


def _usable_length(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 < value <= MAX_CUSTOM_MM
    )
