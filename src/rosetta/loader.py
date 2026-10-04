"""Open an artwork file (SVG, PDF, or PDF-compatible AI) and turn it into plottable shapes."""
from dataclasses import dataclass
from pathlib import Path

from rosetta.errors import ImportProblem
from rosetta.flatten import Shape, flatten_with_report
from rosetta.issues import Issue, pdf_text_issue, scan_document, scan_shapes, scan_skipped
from rosetta.pdf_import import pdf_page_to_svg
from rosetta.svgdoc import normalize

SUPPORTED_EXTENSIONS = (".svg", ".pdf", ".ai")
AFFINITY_EXTENSIONS = (".afdesign", ".afphoto", ".afpub", ".af")


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
    if extension not in SUPPORTED_EXTENSIONS:
        raise ImportProblem(
            f"Rosetta Plotter can't open {extension or 'these'} files. Use SVG, PDF, or AI."
        )
    if not path.is_file():
        raise ImportProblem(f"The file {path.name} can't be found.")

    extra_issues = []
    if extension == ".svg":
        doc = normalize(path.read_bytes())
    else:
        svg_text, has_text = pdf_page_to_svg(path, page)
        doc = normalize(svg_text.encode("utf-8"), source_hint="pdf")
        if has_text:
            extra_issues.append(pdf_text_issue())

    report = flatten_with_report(doc)
    shapes = report.shapes
    issues = (
        scan_document(doc.root, doc.source)
        + scan_skipped(report.skipped)
        + extra_issues
        + scan_shapes(shapes)
    )
    blocking = [issue for issue in issues if issue.blocking]
    if blocking:
        raise ImportProblem(blocking[0].message)
    return Artwork(path.stem, doc.width_mm, doc.height_mm, shapes, issues, doc.source)
