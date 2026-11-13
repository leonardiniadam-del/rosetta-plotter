"""Write the plot-ready SVG the EMS engine plots (spec §6.2 step 8).

Page = the machine's reachable area in mm, so SVG coordinates are machine coordinates.
One Inkscape layer per pen color, numbered from 1, so each color plots as its own
'layers'-mode run with a pen change in between. No XML declaration, so the text can be
passed straight to pyaxidraw's plot_setup().
"""
from lxml import etree

from rosetta.compose import ColorGroup
from rosetta.models import MachineModel
from rosetta.svgdoc import INKSCAPE_NS, SVG_NS


def shift_layer(svg: str, number: int, dx: float, dy: float) -> str:
    """The plot SVG with one pen's layer moved by (dx, dy) mm: a new pen whose nib sits a little off
    the last one's is lined up this way, without touching the other layers."""
    root = etree.fromstring(svg.encode("utf-8"))
    for layer in root:
        if layer.get(f"{{{INKSCAPE_NS}}}label") == str(number):
            layer.set("transform", f"translate({dx:.4f},{dy:.4f})")
            break
    else:
        raise ValueError(f"The plot has no layer {number}.")
    return etree.tostring(root, encoding="unicode")


def plot_svg(model: MachineModel, groups: list[ColorGroup]) -> str:
    travel_x, travel_y = model.travel_mm
    root = etree.Element(f"{{{SVG_NS}}}svg", nsmap={None: SVG_NS, "inkscape": INKSCAPE_NS})
    root.set("width", f"{travel_x:.4f}mm")
    root.set("height", f"{travel_y:.4f}mm")
    root.set("viewBox", f"0 0 {travel_x:.4f} {travel_y:.4f}")
    for number, group in enumerate(groups, start=1):
        layer = etree.SubElement(root, f"{{{SVG_NS}}}g")
        layer.set(f"{{{INKSCAPE_NS}}}groupmode", "layer")
        layer.set(f"{{{INKSCAPE_NS}}}label", str(number))
        for polyline in group.polylines:
            element = etree.SubElement(layer, f"{{{SVG_NS}}}polyline")
            element.set("points", " ".join(f"{x:.4f},{y:.4f}" for x, y in polyline))
            element.set("style", f"fill:none;stroke:{group.color}")
    return etree.tostring(root, encoding="unicode")
