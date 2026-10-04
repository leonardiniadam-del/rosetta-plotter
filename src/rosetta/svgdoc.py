"""Read an SVG from any app and normalize it.

After normalize(): the root has width/height in mm and a viewBox, and <style> rules have
been copied onto elements (see inline_css), so the EMS parser reads the file the way the
student's app drew it.
"""
import re
from dataclasses import dataclass

import tinycss2
from lxml import etree

from rosetta.errors import ImportProblem
from rosetta.units import MM_PER_INCH, length_to_mm, parse_length

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
SODIPODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
SERIF_NS = "http://www.serif.com/"

# What an app means by a size with no unit (or 'px'), in units per inch.
# Illustrator means points; EMS fixes the same thing in process_ai.py. PDF pages are points.
# Affinity is checked against a real Affinity 3.3 export in Task 20.
AFFINITY_PX_PER_INCH = 96.0
IMPLICIT_PX_PER_INCH = {
    "illustrator": 72.0,
    "affinity": AFFINITY_PX_PER_INCH,
    "inkscape": 96.0,
    "svg": 96.0,
    "pdf": 72.0,
}

_PARSER = etree.XMLParser(huge_tree=True, no_network=True)


@dataclass
class NormalizedSvg:
    root: etree._Element
    width_mm: float
    height_mm: float
    source: str  # 'illustrator' | 'affinity' | 'inkscape' | 'svg' | 'pdf'


def detect_source(root: etree._Element, raw: bytes) -> str:
    """Guess which app wrote this SVG from its fingerprints."""
    if b"Adobe Illustrator" in raw[:8192] or b".cls-1" in raw or root.xpath("//*[@data-name]"):
        return "illustrator"
    namespaces = set((root.nsmap or {}).values())
    if SERIF_NS in namespaces:
        return "affinity"
    if INKSCAPE_NS in namespaces or SODIPODI_NS in namespaces:
        return "inkscape"
    return "svg"


def normalize(raw: bytes, source_hint: str | None = None) -> NormalizedSvg:
    try:
        root = etree.fromstring(raw, parser=_PARSER)
    except etree.XMLSyntaxError as exc:
        raise ImportProblem("This file isn't a readable SVG.") from exc
    if not isinstance(root.tag, str) or etree.QName(root).localname != "svg":
        raise ImportProblem("This file isn't a readable SVG.")

    source = source_hint or detect_source(root, raw)
    px_per_inch = IMPLICIT_PX_PER_INCH[source]
    viewbox = _parse_viewbox(root.get("viewBox"))

    width_mm = length_to_mm(root.get("width"), px_per_inch)
    height_mm = length_to_mm(root.get("height"), px_per_inch)
    if width_mm is None or height_mm is None:
        if viewbox is None:
            raise ImportProblem("This file has no page size, so it can't be placed.")
        width_mm = viewbox[2] * MM_PER_INCH / px_per_inch
        height_mm = viewbox[3] * MM_PER_INCH / px_per_inch
    if width_mm <= 0 or height_mm <= 0:
        raise ImportProblem("This file's page size is zero.")
    if viewbox is None:
        viewbox = _implied_viewbox(root, width_mm, height_mm)

    root.set("width", f"{width_mm:.6f}mm")
    root.set("height", f"{height_mm:.6f}mm")
    root.set("viewBox", " ".join(f"{value:.6f}" for value in viewbox))
    inline_css(root)
    return NormalizedSvg(root, width_mm, height_mm, source)


def _parse_viewbox(text: str | None) -> tuple[float, float, float, float] | None:
    if not text:
        return None
    parts = text.replace(",", " ").split()
    if len(parts) != 4:
        return None
    try:
        values = tuple(float(part) for part in parts)
    except ValueError:
        return None
    if values[2] <= 0 or values[3] <= 0:
        return None
    return values


def _implied_viewbox(root, width_mm: float, height_mm: float) -> tuple[float, float, float, float]:
    """No viewBox: user units are the unitless numbers if the size was unitless, else CSS px."""
    width_value, width_unit = parse_length(root.get("width"))
    height_value, height_unit = parse_length(root.get("height"))
    if width_value and height_value and width_unit in ("", "px") and height_unit in ("", "px"):
        return (0.0, 0.0, width_value, height_value)
    return (0.0, 0.0, width_mm * 96.0 / MM_PER_INCH, height_mm * 96.0 / MM_PER_INCH)


_SIMPLE_SELECTOR = re.compile(r"^(?P<tag>[A-Za-z][\w-]*)?(?P<rest>(?:[.#][\w-]+)*)$")


def inline_css(root: etree._Element) -> None:
    """Copy <style> rules onto each element's style attribute.

    The EMS parser ignores <style>, and Illustrator's default export puts every color in
    CSS classes. Supports simple selectors only (tag, .class, #id, and combinations like
    path.cls-1); others are skipped. An element's own style attribute wins.
    """
    rules = []
    for style_element in root.iter(f"{{{SVG_NS}}}style", "style"):
        for rule in tinycss2.parse_stylesheet(
            style_element.text or "", skip_comments=True, skip_whitespace=True
        ):
            if rule.type != "qualified-rule":
                continue
            declarations = {
                declaration.name.lower(): tinycss2.serialize(declaration.value).strip()
                for declaration in tinycss2.parse_declaration_list(
                    rule.content, skip_comments=True, skip_whitespace=True
                )
                if declaration.type == "declaration"
            }
            for selector_text in tinycss2.serialize(rule.prelude).split(","):
                parsed = _parse_selector(selector_text.strip())
                if parsed is not None:
                    specificity, matcher = parsed
                    rules.append((specificity, len(rules), matcher, declarations))
    if not rules:
        return
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        matched = sorted(
            (specificity, order, declarations)
            for specificity, order, matcher, declarations in rules
            if matcher(element)
        )
        if not matched:
            continue
        merged: dict[str, str] = {}
        for _specificity, _order, declarations in matched:
            merged.update(declarations)
        merged.update(_parse_style_attribute(element.get("style")))
        element.set("style", ";".join(f"{key}:{value}" for key, value in merged.items()))


def _parse_selector(text: str):
    """Return (specificity, matcher) for a simple selector, or None if unsupported."""
    match = _SIMPLE_SELECTOR.match(text)
    if not text or not match:
        return None
    tag = match.group("tag")
    parts = re.findall(r"[.#][\w-]+", match.group("rest"))
    classes = {part[1:] for part in parts if part[0] == "."}
    ids = {part[1:] for part in parts if part[0] == "#"}

    def matcher(element) -> bool:
        if tag and etree.QName(element).localname != tag:
            return False
        if ids and element.get("id") not in ids:
            return False
        if classes and not classes.issubset((element.get("class") or "").split()):
            return False
        return True

    return (len(ids), len(classes), 1 if tag else 0), matcher


def _parse_style_attribute(text: str | None) -> dict[str, str]:
    result = {}
    for part in (text or "").split(";"):
        if ":" in part:
            key, value = part.split(":", 1)
            if key.strip():
                result[key.strip().lower()] = value.strip()
    return result
