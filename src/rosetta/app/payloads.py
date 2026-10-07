"""Rosetta's objects as the plain JSON the page receives (documented in docs/bridge.md)."""
import base64

from rosetta.colors import color_name, is_white
from rosetta.compose import CLIP_WARNING_MM, Job, Material, Placement
from rosetta.models import MachineModel

DECIMALS = 2  # 0.01 mm: finer than any AxiDraw draws, and it keeps big files' JSON small


def _rounded(value: float) -> float:
    return round(value, DECIMALS)


def placement_payload(placement: Placement) -> dict:
    return {"x": placement.x, "y": placement.y, "scale": placement.scale, "rotation": placement.rotation}


def piece_payload(piece) -> dict:
    """A piece, with its lines in artwork mm (the page applies the placement itself while dragging)."""
    art = piece.artwork
    groups: dict[str, list] = {}
    for shape in art.shapes:
        lines = groups.setdefault(shape.color, [])
        for polyline in shape.polylines:
            lines.append([_rounded(value) for point in polyline for value in point])
    preview = None
    if art.preview_svg:
        encoded = base64.b64encode(art.preview_svg.encode("utf-8")).decode("ascii")
        preview = f"data:image/svg+xml;base64,{encoded}"
    return {
        "id": piece.id,
        "name": art.name,
        "path": piece.path,
        "page": piece.page,
        "width_mm": art.width_mm,
        "height_mm": art.height_mm,
        "placement": placement_payload(piece.placement),
        "issues": [
            {"code": issue.code, "message": issue.message, "count": issue.count} for issue in art.issues
        ],
        "groups": [
            {"color": color, "name": color_name(color), "white": is_white(color), "lines": lines}
            for color, lines in groups.items()
        ],
        "preview": preview,
    }


def material_payload(material: Material, model: MachineModel | None) -> dict:
    """The paper, plus the plotter's reach and whether the paper fits inside it (unknown without a model)."""
    reach = fits = None
    if model is not None:
        travel_x, travel_y = model.travel_mm
        reach = [travel_x, travel_y]
        fits = (
            material.x + material.width <= travel_x + CLIP_WARNING_MM
            and material.y + material.height <= travel_y + CLIP_WARNING_MM
        )
    return {
        "x": material.x, "y": material.y, "width": material.width, "height": material.height,
        "reach": reach, "fits": fits,
    }


def job_payload(job: Job) -> dict:
    """The pens a job needs, in plot order (the Pens panel)."""
    return {
        "colors": [
            {"layer": number, "color": group.color, "name": group.name, "lines": len(group.polylines)}
            for number, group in enumerate(job.groups, start=1)
        ],
        "ink_bbox": list(job.ink_bbox) if job.ink_bbox else None,
        "clipped": job.clipped,
        "empty": not job.groups,
    }
