"""SVG paint values to pen colors."""
import colorsys

import tinycss2.color3

WHITE = "#ffffff"
BLACK = "#000000"

_CSS_WIDE_KEYWORDS = ("inherit", "initial", "unset", "revert")

_HUE_SECTORS = (
    (15, "red"), (45, "orange"), (70, "yellow"), (165, "green"), (195, "cyan"),
    (255, "blue"), (290, "purple"), (345, "magenta"), (360, "red"),
)


def resolve_paint(value: str | None, default: str | None) -> str | None:
    """Return '#rrggbb' for visible paint, or None for no paint.

    Gradients, patterns, and currentColor can't be known here, so they count as black.
    """
    if value is None:
        value = default
    if value is None:
        return None
    text = value.replace("!important", "").strip()
    if text.lower() in _CSS_WIDE_KEYWORDS:
        return resolve_paint(default, None)
    if text.lower() in ("", "none", "transparent"):
        return None
    if text.lower().startswith("url("):
        return BLACK
    # CSS Color 4 syntax (space-separated rgb(), hsl() with deg, rebeccapurple) isn't
    # recognized by color3 and falls back to black -- design apps don't emit it.
    parsed = tinycss2.color3.parse_color(text)
    if parsed is None or isinstance(parsed, str):  # junk, or the string 'currentColor'
        return BLACK
    if parsed.alpha == 0:
        return None
    return "#" + "".join(
        f"{max(0, min(255, round(c * 255))):02x}" for c in (parsed.red, parsed.green, parsed.blue)
    )


def color_name(hex_color: str) -> str:
    """Everyday name for a '#rrggbb' color, for prompts like 'Load the red pen'.

    Classifies by hue first, then splits off black/gray/white, brown, pink, and purple.
    """
    red, green, blue = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    if value <= 0.15:
        return "black"
    if saturation < 0.18:
        return "white" if value >= 0.9 else "gray"
    degrees = hue * 360
    name = next(label for limit, label in _HUE_SECTORS if degrees < limit)
    if 15 <= degrees < 70 and (value < 0.7 or (saturation < 0.6 and value < 0.8)):
        return "brown"
    if name in ("red", "magenta") and saturation < 0.65 and value > 0.75:
        return "pink"
    if name == "magenta" and value < 0.6:
        return "purple"
    return name
