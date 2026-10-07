"""Rosetta's objects as the plain JSON the page receives (documented in docs/bridge.md)."""
import base64

from rosetta.colors import color_name, is_white
from rosetta.compose import CLIP_WARNING_MM, Job, Material, Placement
from rosetta.models import MachineModel

DECIMALS = 2  # 0.01 mm: finer than any AxiDraw draws, and it keeps big files' JSON small


def _rounded(value: float) -> float:
    return round(value, DECIMALS)


def placement_payload(placement: Placement) -> dict:
    scale_y = placement.scale if placement.scale_y is None else placement.scale_y
    return {
        "x": placement.x, "y": placement.y, "scale": placement.scale,
        "scale_y": scale_y, "rotation": placement.rotation,
    }


def job_payload(job) -> dict:
    """A job in the Jobs list, with its lines in artwork mm (the page places them itself)."""
    art = job.artwork
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
        "id": job.id,
        "name": art.name,
        "path": job.path,
        "page": job.page,
        "width_mm": art.width_mm,
        "height_mm": art.height_mm,
        "issues": [
            {"code": issue.code, "message": issue.message, "count": issue.count} for issue in art.issues
        ],
        "groups": [
            {"color": color, "name": color_name(color), "white": is_white(color), "lines": lines}
            for color, lines in groups.items()
        ],
        "preview": preview,
    }


def piece_payload(piece) -> dict:
    """A placed copy of a job: which job, and where."""
    return {"id": piece.id, "job_id": piece.job_id, "placement": placement_payload(piece.placement)}


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


def colors_payload(job: Job, hidden) -> dict:
    """Every pen color the placed drawings use, in plot order; only visible pens get a layer number."""
    colors, layer = [], 0
    for group in job.groups:
        visible = group.color not in hidden
        if visible:
            layer += 1
        colors.append({
            "layer": layer if visible else None, "color": group.color, "name": group.name,
            "lines": len(group.polylines), "visible": visible,
        })
    return {
        "colors": colors,
        "ink_bbox": list(job.ink_bbox) if job.ink_bbox else None,
        "clipped": job.clipped,
        "empty": not job.groups,
    }
