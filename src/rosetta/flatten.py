"""Normalized SVG -> Shapes, using the EMS digest parser.

Using EMS's own parser means what Rosetta shows on screen is what the engine will draw:
same transforms, same handling of <use>/<symbol>, same curve tolerance (0.002 in).
Like EMS, Inkscape layers whose name starts with '%' (AxiDraw's notes-layer convention) are skipped.
"""
import logging
from dataclasses import dataclass

from axidrawinternal import digest_svg, plot_warnings
from ink_extensions import simpletransform
from plotink import plot_utils

from rosetta.colors import resolve_paint
from rosetta.errors import ImportProblem
from rosetta.svgdoc import NormalizedSvg
from rosetta.units import MM_PER_INCH

CURVE_TOLERANCE_IN = 0.002  # EMS default curve_tolerance (0.05 mm)
ALL_LAYERS = -2  # EMS layer_selection value meaning "every layer"

logger = logging.getLogger(__name__)

Polyline = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Shape:
    """One SVG drawing element, as straight-line polylines in mm (document coordinates)."""

    polylines: tuple[Polyline, ...]
    color: str  # '#rrggbb': the stroke color, or the fill color for fill-only shapes
    stroked: bool
    filled: bool


@dataclass(frozen=True)
class Flattened:
    shapes: list[Shape]
    skipped: frozenset[str]  # element types EMS reached but can't draw, e.g. {"text", "image"}


def flatten(doc: NormalizedSvg) -> list[Shape]:
    return flatten_with_report(doc).shapes


def flatten_with_report(doc: NormalizedSvg) -> Flattened:
    root = doc.root
    width_in = doc.width_mm / MM_PER_INCH
    height_in = doc.height_mm / MM_PER_INCH
    # Same document transform EMS builds in AxiDraw.prepare_document().
    s_x, s_y, o_x, o_y = plot_utils.vb_scale(
        root.get("viewBox"), root.get("preserveAspectRatio"), width_in, height_in
    )
    transform = simpletransform.parseTransform(
        f"scale({s_x:.6E},{s_y:.6E}) translate({o_x:.6E},{o_y:.6E})"
    )
    warnings = plot_warnings.PlotWarnings()
    digester = digest_svg.DigestSVG(default_logging=False)
    try:
        digest = digester.process_svg(
            root,
            warnings,
            [width_in, height_in, s_x, s_y, ALL_LAYERS, CURVE_TOLERANCE_IN],
            transform,
        )
    except Exception as exc:  # EMS's parser raises many types on odd input; the student needs a message
        logger.debug("EMS parser failed", exc_info=True)
        raise ImportProblem("This file couldn't be read. Try exporting it again as SVG or PDF.") from exc

    shapes = []
    for layer in digest.layers:
        for item in layer.paths:
            subpaths = [subpath for subpath in item.subpaths if _has_length(subpath)]
            if not subpaths:
                continue
            stroke = resolve_paint(item.stroke, default=None)
            fill = resolve_paint(item.fill, default="black")  # SVG's default fill is black
            if all(len(subpath) == 2 for subpath in subpaths):
                fill = None  # single segments enclose no area; EMS strips their fill too
            if stroke is None and fill is None:
                continue  # invisible helper shape
            if stroke is None:  # a fill implies a closed outline
                subpaths = [_closed(subpath) for subpath in subpaths]
            polylines = tuple(
                tuple((x * MM_PER_INCH, y * MM_PER_INCH) for x, y in subpath)
                for subpath in subpaths
            )
            shapes.append(Shape(polylines, stroke or fill, stroke is not None, fill is not None))
    return Flattened(shapes, frozenset(warnings.warning_dict))


def _has_length(subpath) -> bool:
    """At least two points, and not all the same point."""
    return len(subpath) >= 2 and any(point != subpath[0] for point in subpath)


def _closed(subpath):
    if len(subpath) >= 3 and subpath[-1] != subpath[0]:
        return [*subpath, subpath[0]]
    return subpath
