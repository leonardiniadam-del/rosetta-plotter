"""Put artwork on paper: placement, clipping to paper and machine reach, grouping by pen color."""
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rosetta.colors import color_name, is_white
from rosetta.geometry import (
    Point, Rect, bbox, clip_polyline, contains, intersect, place_point,
)
from rosetta.models import MachineModel

if TYPE_CHECKING:
    from rosetta.loader import Artwork

DEFAULT_MARGIN_MM = 6.35  # 0.25 in
SAME_SIZE_TOLERANCE_MM = 1.0
# EMS doesn't draw lines lying exactly on the plot page's far (max x / max y) edges, and the
# page is the machine's reach, so keep everything this far inside them.
REACH_EDGE_INSET_MM = 0.01
# Cuts smaller than this aren't worth a warning (e.g. A3 paper is 297 mm but the A3 plotter
# reaches 296.93 mm). Matches EMS's own bounds tolerance (0.003 in).
CLIP_WARNING_MM = 0.08


@dataclass(frozen=True)
class Material:
    """Paper on the bed. (x, y) is its corner nearest Home, in machine mm."""

    x: float
    y: float
    width: float
    height: float

    @property
    def rect(self) -> Rect:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


@dataclass(frozen=True)
class Placement:
    """Where a piece sits on the paper: the top-left of its turned, scaled artwork's upright box at (x, y).

    scale stretches the artwork along its own width and scale_y along its own height (None: the same as
    scale); rotation turns it clockwise, in degrees. Frozen so duplicated pieces can't share a placement
    by accident; use dataclasses.replace.
    """

    x: float = 0.0
    y: float = 0.0
    scale: float = 1.0
    rotation: float = 0  # clockwise degrees, any finite angle
    scale_y: float | None = None  # None: the same as scale


@dataclass
class PlacedPiece:
    artwork: "Artwork"
    placement: Placement


@dataclass
class ColorGroup:
    color: str
    polylines: list[list[Point]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return color_name(self.color)


@dataclass
class Job:
    groups: list[ColorGroup]  # plot order; layer number = index + 1
    ink_bbox: Rect | None  # bounds of everything that will be drawn (for Trace outline)
    clipped: bool  # True if more than CLIP_WARNING_MM was cut off at the paper edge or machine reach


def compose_job(
    model: MachineModel,
    material: Material,
    pieces: list[PlacedPiece],
    skip_white: bool = True,
    skip_colors: frozenset[str] = frozenset(),
) -> Job:
    """Place every piece on the paper, clip to paper ∩ machine reach, and group lines by pen
    color in order of first appearance (pieces in list order; a color whose first shapes are
    clipped away entirely moves later). Colors in skip_colors (lowercase '#rrggbb') are left
    out, like hidden pens."""
    _check_material(material)
    travel_x, travel_y = model.travel_mm
    reach = (0.0, 0.0, travel_x - REACH_EDGE_INSET_MM, travel_y - REACH_EDGE_INSET_MM)
    clip_rect = intersect(material.rect, reach)
    # The reach inset is Rosetta's own safety margin, not a cut the student made, so the
    # warning measures against the real reach.
    warn_rect = intersect(material.rect, (0.0, 0.0, travel_x, travel_y))
    groups: dict[str, ColorGroup] = {}
    clipped = False
    for piece in pieces:
        art, placement = piece.artwork, piece.placement
        _check_placement(placement)
        for shape in art.shapes:
            if skip_white and is_white(shape.color):
                continue
            if shape.color in skip_colors:
                continue
            for polyline in shape.polylines:
                placed = [
                    place_point(
                        point, art.width_mm, art.height_mm, placement.x, placement.y,
                        placement.scale, placement.rotation, (material.x, material.y),
                        placement.scale_y,
                    )
                    for point in polyline
                ]
                if clip_rect is None or warn_rect is None:
                    clipped = True
                    continue
                if not all(contains(warn_rect, point, CLIP_WARNING_MM) for point in placed):
                    clipped = True
                parts = clip_polyline(placed, clip_rect)
                if parts:
                    groups.setdefault(shape.color, ColorGroup(shape.color)).polylines.extend(parts)
    kept = list(groups.values())
    return Job(kept, bbox([line for group in kept for line in group.polylines]), clipped)


def _check_material(material: Material) -> None:
    """The paper comes from the UI too; refuse sizes and positions that would break the clip."""
    if not (
        math.isfinite(material.x)
        and math.isfinite(material.y)
        and math.isfinite(material.width)
        and math.isfinite(material.height)
        and material.width > 0
        and material.height > 0
    ):
        raise ValueError(f"Paper size and position must be positive, finite numbers: {material}")


def _check_placement(placement: Placement) -> None:
    """Placements come from the UI; refuse values that would put NaN or mirrored art in the plot."""
    if not (math.isfinite(placement.x) and math.isfinite(placement.y)):
        raise ValueError(f"Placement position must be finite: {placement}")
    for name in ("scale", "scale_y"):
        value = getattr(placement, name)
        if name == "scale_y" and value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not (math.isfinite(value) and value > 0):
            raise ValueError(f"Placement {name} must be a positive number: {placement}")
    rotation = placement.rotation
    if isinstance(rotation, bool) or not isinstance(rotation, (int, float)) or not math.isfinite(rotation):
        raise ValueError(f"Placement rotation must be a finite number of degrees: {placement}")


def initial_placement(
    artwork: "Artwork", material: Material, margin: float = DEFAULT_MARGIN_MM
) -> Placement:
    """Where a newly imported piece lands (spec §5, step 3).

    Artwork drawn at the paper's size lands exactly on the paper, shrunk by the fraction of a
    millimetre it may overhang so no edge gets cut. Anything else is centered and shrunk,
    never enlarged, to fit inside the margins.
    """
    if (
        abs(artwork.width_mm - material.width) <= SAME_SIZE_TOLERANCE_MM
        and abs(artwork.height_mm - material.height) <= SAME_SIZE_TOLERANCE_MM
    ):
        scale = min(1.0, material.width / artwork.width_mm, material.height / artwork.height_mm)
        return Placement(0.0, 0.0, scale, 0)
    usable_width = max(material.width - 2 * margin, 1.0)
    usable_height = max(material.height - 2 * margin, 1.0)
    scale = min(1.0, usable_width / artwork.width_mm, usable_height / artwork.height_mm)
    width, height = artwork.width_mm * scale, artwork.height_mm * scale
    return Placement((material.width - width) / 2, (material.height - height) / 2, scale, 0)
