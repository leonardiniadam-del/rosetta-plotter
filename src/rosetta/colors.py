"""SVG paint values to pen colors."""
import tinycss2.color3

WHITE = "#ffffff"
BLACK = "#000000"

_EVERYDAY = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "pink": (255, 192, 203),
    "brown": (139, 69, 19),
    "gray": (128, 128, 128),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
}


def resolve_paint(value: str | None, default: str | None) -> str | None:
    """Return '#rrggbb' for visible paint, or None for no paint.

    Gradients, patterns, and currentColor can't be known here, so they count as black.
    """
    if value is None:
        value = default
    if value is None:
        return None
    text = value.strip()
    if text.lower() in ("", "none", "transparent"):
        return None
    if text.lower().startswith("url("):
        return BLACK
    parsed = tinycss2.color3.parse_color(text)
    if parsed is None or isinstance(parsed, str):  # junk, or the string 'currentColor'
        return BLACK
    if parsed.alpha == 0:
        return None
    return "#{:02x}{:02x}{:02x}".format(
        round(parsed.red * 255), round(parsed.green * 255), round(parsed.blue * 255)
    )


def color_name(hex_color: str) -> str:
    """Closest everyday color name, for prompts like 'Load the red pen'."""
    rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return min(
        _EVERYDAY,
        key=lambda name: sum((a - b) ** 2 for a, b in zip(rgb, _EVERYDAY[name])),
    )
