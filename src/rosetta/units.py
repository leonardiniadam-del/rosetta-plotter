"""Length parsing and conversion. Everything inside Rosetta Plotter is millimetres."""
import re

MM_PER_INCH = 25.4

_ABSOLUTE_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "in": MM_PER_INCH,
    "pt": MM_PER_INCH / 72,
    "pc": MM_PER_INCH / 6,
    "q": 0.25,
}

_LENGTH = re.compile(r"\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Z%]*)\s*")


def parse_length(text: str | None) -> tuple[float | None, str]:
    """Split '12.5mm' into (12.5, 'mm'). Unitless gives ''. Unparseable gives (None, '')."""
    if text is None:
        return None, ""
    match = _LENGTH.fullmatch(text)
    if not match:
        return None, ""
    return float(match.group(1)), match.group(2).lower()


def length_to_mm(text: str | None, px_per_inch: float) -> float | None:
    """Convert an SVG length to mm. Unitless and 'px' use px_per_inch. None for %, em, or junk."""
    value, unit = parse_length(text)
    if value is None:
        return None
    if unit in ("", "px"):
        return value * MM_PER_INCH / px_per_inch
    factor = _ABSOLUTE_MM.get(unit)
    return None if factor is None else value * factor
