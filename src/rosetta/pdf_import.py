"""PDF and PDF-compatible .ai pages -> SVG text, via PyMuPDF (text converted to outlines)."""
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from lxml import etree

from rosetta.colors import BLACK, is_white, resolve_paint
from rosetta.errors import ImportProblem
from rosetta.svgdoc import SVG_NS, SVG_PARSER

pymupdf.TOOLS.mupdf_display_errors(False)  # keeps "MuPDF error:" lines out of the console

AI_NOT_PDF = (
    "This Illustrator file was saved without PDF compatibility. In Illustrator, use "
    "File › Save As and check “Create PDF Compatible File”, or export an SVG instead."
)
NOT_A_PDF = "This file isn't a PDF. Export it from your design app as PDF or SVG."
UNREADABLE = "This PDF can't be read."
PASSWORD_PROTECTED = "This PDF is password-protected. Remove the password and export it again."

_IMAGE = f"{{{SVG_NS}}}image"
_PATH = f"{{{SVG_NS}}}path"
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
_INVISIBLE_TEXT = 3  # text render mode 3 (e.g. an OCR layer): present but never painted
_CLIP_TOLERANCE_PT = 1.0  # clips this close to the page edge are the page-sized kind


@dataclass(frozen=True)
class PdfPage:
    svg: str
    has_text: bool  # visible text (converted to outlines in the SVG)
    has_clip: bool  # a clipping mask smaller than the page: hidden parts would be drawn
    page_count: int


def page_count(path: Path) -> int:
    with _open(Path(path)) as doc:
        return doc.page_count


def pdf_page_to_svg(path: Path, page_index: int = 0) -> PdfPage:
    """One page as SVG text (width and height set in pt from the page), plus what to warn about."""
    with _open(Path(path)) as doc:
        count = doc.page_count
        if count == 0:
            raise ImportProblem("This PDF has no pages.")
        if not 0 <= page_index < count:  # page_index counts from 0; people count from 1
            name = Path(path).name
            if count == 1:
                raise ImportProblem(f"{name} has 1 page; choose page 1.")
            raise ImportProblem(f"{name} has {count} pages; choose a page from 1 to {count}.")
        try:
            page = doc[page_index]
            svg_text = page.get_svg_image(matrix=pymupdf.Identity, text_as_path=True)
            has_text = any(span["type"] != _INVISIBLE_TEXT for span in page.get_texttrace())
            has_clip = _has_clip(page)
            width_pt, height_pt = page.rect.width, page.rect.height
        except ImportProblem:
            raise
        except Exception as exc:  # PyMuPDF raises several exception types for damaged pages
            raise ImportProblem(UNREADABLE) from exc

    try:
        root = etree.fromstring(svg_text.encode("utf-8"), parser=SVG_PARSER)
    except etree.XMLSyntaxError as exc:
        raise ImportProblem(UNREADABLE) from exc
    _blank_image_data(root)
    _drop_fills_under_their_outlines(root)
    root.set("width", f"{width_pt:.4f}pt")
    root.set("height", f"{height_pt:.4f}pt")
    if not root.get("viewBox"):
        root.set("viewBox", f"0 0 {width_pt:.4f} {height_pt:.4f}")
    return PdfPage(etree.tostring(root, encoding="unicode"), has_text, has_clip, count)


def _blank_image_data(root: etree._Element) -> None:
    """Pictures are embedded as base64 (megabytes of it). EMS only needs the tag to report them."""
    for image in root.iter(_IMAGE):
        image.set(_XLINK_HREF, "")
        if image.get("href") is not None:
            image.set("href", "")


def _drop_fills_under_their_outlines(root: etree._Element) -> None:
    """MuPDF writes a shape that is filled and stroked as two paths in a row: the fill (no stroke),
    then the same outline stroked (no fill). Rosetta draws outlines, so keeping both would draw the
    outline twice (two colors would also add a pen color and a "solid fills" warning for the fill).

    The fill goes, unless its outline is white: white is skipped later, and the shape must not vanish.
    """
    for path in list(root.iter(_PATH)):
        outline = path.getnext()
        if (
            outline is not None
            and outline.tag == _PATH
            and _is_fill_only(path)
            and _is_stroke_only(outline)
            and path.get("d") == outline.get("d")
            and path.get("transform") == outline.get("transform")
            and not is_white(resolve_paint(outline.get("stroke"), default=BLACK) or BLACK)
        ):
            path.getparent().remove(path)


def _is_fill_only(path: etree._Element) -> bool:
    return path.get("fill", "").strip() != "none" and path.get("stroke", "none").strip() == "none"


def _is_stroke_only(path: etree._Element) -> bool:
    return path.get("fill", "").strip() == "none" and path.get("stroke", "none").strip() != "none"


def _has_clip(page) -> bool:
    """True if a clipping mask is meaningfully smaller than the page.

    Illustrator, Affinity and MuPDF itself wrap content in page-sized clips, which hide nothing.
    get_drawings reports scissors in the page's unrotated space, so compare to the unrotated page.
    """
    bounds = page.rect * page.derotation_matrix
    return any(
        item["type"] == "clip" and _cuts_into_page(item["scissor"], bounds)
        for item in page.get_drawings(extended=True)
    )


def _cuts_into_page(scissor, bounds) -> bool:
    tolerance = _CLIP_TOLERANCE_PT
    return (
        scissor.x0 - bounds.x0 > tolerance
        or scissor.y0 - bounds.y0 > tolerance
        or bounds.x1 - scissor.x1 > tolerance
        or bounds.y1 - scissor.y1 > tolerance
    )


def _open(path: Path):
    with open(path, "rb") as handle:
        head = handle.read(1024)
    if b"%PDF-" not in head:
        raise ImportProblem(AI_NOT_PDF if path.suffix.lower() == ".ai" else NOT_A_PDF)
    try:
        doc = pymupdf.open(path, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several exception types for damaged files
        raise ImportProblem(UNREADABLE) from exc
    if doc.needs_pass:
        doc.close()
        raise ImportProblem(PASSWORD_PROTECTED)
    return doc
