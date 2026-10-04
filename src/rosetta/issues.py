"""Find things in a file that won't plot the way the student expects, and say so plainly."""
from dataclasses import dataclass

from lxml import etree

from rosetta.colors import WHITE
from rosetta.svgdoc import SVG_NS


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    count: int = 1
    blocking: bool = False


MESSAGES = {
    "text": "This file has live text, which can't be drawn. In Illustrator or Affinity, "
            "convert text to outlines and export again.",
    "image": "Pictures can't be drawn, only lines. The picture will be skipped.",
    "clip": "This file uses a clipping mask. The hidden parts will be drawn too. "
            "Release or expand the mask before exporting.",
    "fill_only": "Some shapes are solid fills. The plotter draws only their outlines.",
    "white": "There's a white shape here, probably a background. It will be skipped.",
    "pdf_text": "Text will be drawn as outlined letters (double lines).",
    "empty": "This file has no lines to draw.",
}

_NS = {"svg": SVG_NS}


def scan_document(root: etree._Element, source: str) -> list[Issue]:
    counts = {"text": 0, "image": 0, "clip": 0}
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        name = etree.QName(element).localname
        if name in ("text", "flowRoot") and not _in_defs(element):
            counts["text"] += 1
        elif name == "image" and not _in_defs(element):
            counts["image"] += 1
        # PDF conversions wrap content in clip groups, so masks can't be told apart there.
        if source != "pdf" and _uses_clip(element):
            counts["clip"] += 1
    return [Issue(code, MESSAGES[code], count) for code, count in counts.items() if count]


def scan_shapes(shapes) -> list[Issue]:
    if not shapes:
        return [Issue("empty", MESSAGES["empty"], blocking=True)]
    issues = []
    fill_only = sum(1 for shape in shapes if shape.filled and not shape.stroked)
    white = sum(1 for shape in shapes if shape.color == WHITE)
    if fill_only:
        issues.append(Issue("fill_only", MESSAGES["fill_only"], fill_only))
    if white:
        issues.append(Issue("white", MESSAGES["white"], white))
    return issues


def pdf_text_issue() -> Issue:
    return Issue("pdf_text", MESSAGES["pdf_text"])


def _in_defs(element) -> bool:
    return bool(element.xpath("ancestor::svg:defs", namespaces=_NS))


def _uses_clip(element) -> bool:
    if element.get("clip-path") or element.get("mask"):
        return True
    style = (element.get("style") or "").replace(" ", "")
    return "clip-path:url" in style or "mask:url" in style
