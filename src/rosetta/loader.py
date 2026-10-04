"""Open an artwork file (SVG, PDF, or PDF-compatible AI) and turn it into plottable shapes."""
from dataclasses import dataclass, replace
from pathlib import Path

from rosetta.errors import ImportProblem
from rosetta.flatten import Shape, flatten_with_report
from rosetta.geometry import clip_polyline
from rosetta.issues import (
    MESSAGES,
    Issue,
    pdf_text_issue,
    scan_document,
    scan_shapes,
    scan_skipped,
)
from rosetta.pdf_import import pdf_page_to_svg
from rosetta.svgdoc import normalize

SUPPORTED_EXTENSIONS = (".svg", ".pdf", ".ai")
AFFINITY_EXTENSIONS = (".afdesign", ".afphoto", ".afpub", ".af")
# Issues that explain why a file drew nothing; they say more than a bare "no lines to draw".
_SKIPPED_CODES = ("text", "image", "unsupported")


@dataclass
class Artwork:
    name: str
    width_mm: float  # the document/artboard size, used as the piece's frame
    height_mm: float
    shapes: list[Shape]
    issues: list[Issue]
    source: str


def load_artwork(path: Path, page: int = 0) -> Artwork:
    path = Path(path)
    extension = path.suffix.lower()
    if extension in AFFINITY_EXTENSIONS:
        raise ImportProblem(
            "Affinity files can't be opened directly. In Affinity, use File › Export › "
            "SVG or PDF, then import that file."
        )
    if extension == ".svgz":
        raise ImportProblem("Compressed SVG (.svgz) isn't supported. Export a plain SVG instead.")
    if extension not in SUPPORTED_EXTENSIONS:
        raise ImportProblem(
            f"Rosetta Plotter can't open {extension or 'these'} files. Use SVG, PDF, or AI."
        )
    if not path.is_file():
        raise ImportProblem(f"The file {path.name} can't be found.")

    if extension == ".svg":
        doc, name, extra_issues = _read_svg(path)
    else:
        doc, name, extra_issues = _read_pdf(path, page)

    report = flatten_with_report(doc)
    shapes = report.shapes
    if doc.source == "pdf":
        shapes = _clip_to_page(shapes, doc.width_mm, doc.height_mm)
    issues = (
        scan_document(doc.root, doc.source)
        + scan_skipped(report.skipped)
        + extra_issues
        + scan_shapes(shapes)
    )
    blocking = [issue for issue in issues if issue.blocking]
    if blocking:
        explained = [issue.message for issue in issues if issue.code in _SKIPPED_CODES]
        raise ImportProblem(" ".join(explained) if explained else blocking[0].message)
    return Artwork(name, doc.width_mm, doc.height_mm, shapes, issues, doc.source)


def _clip_to_page(shapes: list[Shape], width_mm: float, height_mm: float) -> list[Shape]:
    """A PDF hides anything outside its page box; drop it so it isn't drawn either."""
    page = (0.0, 0.0, width_mm, height_mm)
    kept = []
    for shape in shapes:
        polylines = tuple(
            tuple(run) for line in shape.polylines for run in clip_polyline(line, page)
        )
        if polylines:
            kept.append(replace(shape, polylines=polylines))
    return kept


def _read_svg(path: Path):
    """(normalized document, artwork name, issues found while reading)"""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise _unreadable(path) from exc
    return normalize(raw), path.stem, []


def _read_pdf(path: Path, page: int):
    """(normalized document, artwork name, issues found while reading)"""
    try:
        pdf_page = pdf_page_to_svg(path, page)
    except OSError as exc:
        raise _unreadable(path) from exc
    doc = normalize(pdf_page.svg.encode("utf-8"), source_hint="pdf")
    issues = []
    if pdf_page.has_text:
        issues.append(pdf_text_issue())
    if pdf_page.has_clip:
        issues.append(Issue("clip", MESSAGES["clip"]))
    name = f"{path.stem} (page {page + 1})" if pdf_page.page_count > 1 else path.stem
    return doc, name, issues


def _unreadable(path: Path) -> ImportProblem:
    return ImportProblem(
        f"Rosetta Plotter couldn't read {path.name}. "
        "If it's open in another program, close it and try again."
    )
