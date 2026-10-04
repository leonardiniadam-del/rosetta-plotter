from rosetta.colors import BLACK, WHITE, color_name, resolve_paint


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


def test_color_name_finds_nearest_everyday_name():
    assert color_name("#e30613") == "red"
    assert color_name("#000000") == "black"
    assert color_name("#0000ff") == "blue"
    assert color_name("#7f7f7f") == "gray"
