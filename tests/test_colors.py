import pytest

from rosetta.colors import BLACK, WHITE, color_name, is_white, resolve_paint


def test_resolve_paint_normalizes_to_hex():
    assert resolve_paint("#f00", default=None) == "#ff0000"
    assert resolve_paint("red", default=None) == "#ff0000"
    assert resolve_paint("rgb(0, 0, 255)", default=None) == "#0000ff"
    assert resolve_paint("#FFFFFF", default=None) == WHITE


def test_resolve_paint_none_and_transparent_mean_no_paint():
    assert resolve_paint("none", default=None) is None
    assert resolve_paint("rgba(0,0,0,0)", default=None) is None
    assert resolve_paint(None, default=None) is None


def test_resolve_paint_uses_default_when_unset():
    # SVG's default fill is black.
    assert resolve_paint(None, default="black") == BLACK


def test_resolve_paint_unknown_paints_count_as_black():
    assert resolve_paint("url(#gradient1)", default=None) == BLACK
    assert resolve_paint("currentColor", default=None) == BLACK


def test_resolve_paint_clamps_out_of_range_channels():
    assert resolve_paint("rgb(300,0,0)", default=None) == "#ff0000"
    assert resolve_paint("rgb(-5,0,0)", default=None) == "#000000"


def test_resolve_paint_blank_and_case():
    assert resolve_paint("  ", default=None) is None
    assert resolve_paint("NONE", default=None) is None


def test_resolve_paint_css_wide_keywords_use_default():
    assert resolve_paint("inherit", default=None) is None
    assert resolve_paint("Inherit !important", default=None) is None
    assert resolve_paint("initial", default="black") == BLACK


@pytest.mark.parametrize(
    "hex_color, name",
    [
        ("#e30613", "red"), ("#8b0000", "red"), ("#000000", "black"), ("#0000ff", "blue"),
        ("#1b1464", "blue"), ("#7f7f7f", "gray"), ("#404040", "gray"), ("#c0c0c0", "gray"),
        ("#ffffff", "white"), ("#f5f5f5", "white"), ("#39b54a", "green"), ("#8dc63f", "green"),
        ("#ec008c", "magenta"), ("#a67c52", "brown"), ("#c69c6d", "brown"), ("#8b4513", "brown"),
        ("#ffa500", "orange"), ("#ffff00", "yellow"), ("#ffc0cb", "pink"), ("#ff69b4", "pink"),
        ("#800080", "purple"), ("#00ffff", "cyan"),
    ],
)
def test_color_name_by_hue(hex_color, name):
    assert color_name(hex_color) == name


def test_near_white_rule_is_shared():
    assert color_name("#e6e6e6") == "gray"
    assert is_white("#fefefe") and is_white("#f5f5f5") and not is_white("#e6e6e6")
