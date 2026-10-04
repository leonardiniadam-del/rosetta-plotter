"""PDF and PDF-compatible .ai pages -> SVG text, via PyMuPDF (text converted to outlines)."""
from pathlib import Path

import pymupdf
from lxml import etree

from rosetta.errors import ImportProblem

AI_NOT_PDF = (
    "This Illustrator file was saved without PDF compatibility. In Illustrator, use "
    "File › Save As and check “Create PDF Compatible File”, or export an SVG instead."
)


def page_count(path: Path) -> int:
    with _open(Path(path)) as doc:
        return doc.page_count


def pdf_page_to_svg(path: Path, page_index: int = 0) -> tuple[str, bool]:
    """Return (svg_text, has_text). The SVG's width and height are set in pt from the page."""
    with _open(Path(path)) as doc:
        if doc.page_count == 0:
            raise ImportProblem("This PDF has no pages.")
        if not 0 <= page_index < doc.page_count:
            raise ImportProblem(
                f"This PDF has {doc.page_count} pages; page {page_index + 1} doesn't exist."
            )
        page = doc[page_index]
        svg_text = page.get_svg_image(matrix=pymupdf.Identity, text_as_path=True)
        has_text = bool(page.get_text().strip())
        width_pt, height_pt = page.rect.width, page.rect.height

    root = etree.fromstring(svg_text.encode("utf-8"))
    root.set("width", f"{width_pt:.4f}pt")
    root.set("height", f"{height_pt:.4f}pt")
    if not root.get("viewBox"):
        root.set("viewBox", f"0 0 {width_pt:.4f} {height_pt:.4f}")
    return etree.tostring(root, encoding="unicode"), has_text


def _open(path: Path):
    with open(path, "rb") as handle:
        head = handle.read(1024)
    if b"%PDF-" not in head:
        if path.suffix.lower() == ".ai":
            raise ImportProblem(AI_NOT_PDF)
        raise ImportProblem("This PDF can't be read.")
    try:
        return pymupdf.open(path, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several exception types for damaged files
        raise ImportProblem("This PDF can't be read.") from exc
