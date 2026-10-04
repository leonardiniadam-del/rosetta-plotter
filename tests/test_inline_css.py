from lxml import etree

from rosetta.svgdoc import inline_css, normalize
from tests import samples

SVG = "http://www.w3.org/2000/svg"


def _root(body: str):
    return etree.fromstring(
        f'<svg xmlns="{SVG}" width="10mm" height="10mm" viewBox="0 0 10 10">{body}</svg>'.encode()
    )


def _style(element) -> dict:
    return dict(p.split(":", 1) for p in element.get("style").split(";") if p)


def test_class_rule_is_copied_to_style():
    root = _root('<style>.cls-1{fill:none;stroke:#ff0000}</style><rect class="cls-1" width="5" height="5"/>')
    inline_css(root)
    rect = root.find(f"{{{SVG}}}rect")
    assert _style(rect) == {"fill": "none", "stroke": "#ff0000"}


def test_inline_style_wins_over_stylesheet():
    root = _root('<style>.a{stroke:red}</style><rect class="a" style="stroke:blue" width="5" height="5"/>')
    inline_css(root)
    assert _style(root.find(f"{{{SVG}}}rect"))["stroke"] == "blue"


def test_specificity_id_beats_class_beats_tag():
    root = _root(
        "<style>#x{stroke:green} .a{stroke:red} rect{stroke:black}</style>"
        '<rect id="x" class="a" width="1" height="1"/><rect class="a" width="1" height="1"/>'
        '<rect width="1" height="1"/>'
    )
    inline_css(root)
    strokes = [_style(r)["stroke"] for r in root.iter(f"{{{SVG}}}rect")]
    assert strokes == ["green", "red", "black"]


def test_selector_lists_and_tag_with_class():
    root = _root('<style>.a, .b{stroke:red} path.c{fill:blue}</style>'
                 '<rect class="b" width="1" height="1"/><path class="c" d="M0,0 L1,1"/>')
    inline_css(root)
    assert _style(root.find(f"{{{SVG}}}rect"))["stroke"] == "red"
    assert _style(root.find(f"{{{SVG}}}path"))["fill"] == "blue"


def test_unsupported_selectors_are_ignored():
    root = _root('<style>g > rect{stroke:red} rect:hover{stroke:blue}</style><g><rect width="1" height="1"/></g>')
    inline_css(root)
    assert root.find(f".//{{{SVG}}}rect").get("style") is None


def test_normalize_runs_inline_css_on_illustrator_export():
    doc = normalize(samples.ILLUSTRATOR_EXPORT)
    rect = doc.root.find(f"{{{SVG}}}rect")
    assert _style(rect) == {"fill": "none", "stroke": "#ff0000"}


def test_style_is_reduced_to_properties_ems_reads():
    root = _root('<rect style="stroke:red;font-family:&quot;A;B&quot;;fill:url(data:image/png;base64,AAA);stroke-width:2" width="1" height="1"/>')
    inline_css(root)
    assert _style(root.find(f"{{{SVG}}}rect")) == {"stroke": "red"}


def test_group_class_is_written_so_children_inherit():
    root = _root('<style>.g{stroke:red}</style><g class="g"><path d="M0,0 L1,1"/></g>')
    inline_css(root)
    assert _style(root.find(f"{{{SVG}}}g")) == {"stroke": "red"}


def test_multiple_style_blocks_cdata_comments_and_at_rules():
    root = _root(
        "<style><![CDATA[.a{stroke:red}]]></style>"
        "<style>/* note */ .b{FILL:blue} @media print{.a{stroke:green}}</style>"
        '<rect class="a b" width="1" height="1"/>'
    )
    inline_css(root)
    assert _style(root.find(f"{{{SVG}}}rect")) == {"stroke": "red", "fill": "blue"}


def test_source_order_breaks_specificity_ties():
    root = _root('<style>.a{stroke:red} .b{stroke:blue}</style><rect class="a b" width="1" height="1"/>')
    inline_css(root)
    assert _style(root.find(f"{{{SVG}}}rect"))["stroke"] == "blue"


def test_inline_css_is_idempotent():
    root = _root('<style>.a{stroke:red}</style><rect class="a" style="fill:none" width="1" height="1"/>')
    inline_css(root)
    first = root.find(f"{{{SVG}}}rect").get("style")
    inline_css(root)
    assert root.find(f"{{{SVG}}}rect").get("style") == first
