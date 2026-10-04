"""Find things in a file that won't plot the way the student expects, and say so plainly."""
from dataclasses import dataclass

from lxml import etree

from rosetta.colors import is_white
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
    "unsupported": "Some parts of this file use features the plotter can't draw, and will be skipped.",
    "clip": "This file uses a clipping mask. The hidden parts will be drawn too. "
            "Release or expand the mask before exporting.",
    "fill_only": "Some shapes are solid fills. The plotter draws only their outlines.",
    "white": "There's a white shape here, probably a background. It will be skipped.",
    "pdf_text": "Text will be drawn as outlined letters (double lines).",
    "empty": "This file has no lines to draw.",
}

_NS = {"svg": SVG_NS}


def scan_document(root: etree._Element, source: str) -> list[Issue]:
    """Clipping masks. EMS draws masked-away parts in full and doesn't warn about them."""
    if source == "pdf":
        return []  # PDF conversions wrap content in clip groups, so masks can't be told apart there.
    clips = sum(
        1
        for element in root.iter()
        if isinstance(element.tag, str) and _uses_clip(element) and not _in_definitions(element)
    )
    return [Issue("clip", MESSAGES["clip"], clips)] if clips else []


def scan_skipped(skipped: frozenset[str]) -> list[Issue]:
    """Things EMS reached while reading the drawing but can't plot (see flatten_with_report)."""
    issues = [Issue(code, MESSAGES[code]) for code in ("text", "image") if code in skipped]
    other = skipped - {"text", "image"}
    if other:
        issues.append(Issue("unsupported", MESSAGES["unsupported"], len(other)))
    return issues


def scan_shapes(shapes) -> list[Issue]:
    if not shapes:
        return [Issue("empty", MESSAGES["empty"], blocking=True)]
    issues = []
    fill_only = sum(
        1 for shape in shapes if shape.filled and not shape.stroked and not is_white(shape.color)
    )
    white = sum(1 for shape in shapes if is_white(shape.color))
    if fill_only:
        issues.append(Issue("fill_only", MESSAGES["fill_only"], fill_only))
    if white:
        issues.append(Issue("white", MESSAGES["white"], white))
    return issues


def pdf_text_issue() -> Issue:
    return Issue("pdf_text", MESSAGES["pdf_text"])


def _in_definitions(element) -> bool:
    return bool(
        element.xpath(
            "boolean(ancestor::svg:defs | ancestor::svg:clipPath | ancestor::svg:mask)",
            namespaces=_NS,
        )
    )


def _uses_clip(element) -> bool:
    for name in ("clip-path", "mask"):
        value = element.get(name)
        if value is not None and value.strip().lower() not in ("", "none"):
            return True
    style = (element.get("style") or "").replace(" ", "")
    return "clip-path:url" in style or "mask:url" in style
