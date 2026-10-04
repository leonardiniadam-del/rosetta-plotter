"""Small helpers shared by tests (kept in the package so tests import one place)."""


def shapes_bbox(shapes) -> tuple[float, float, float, float]:
    xs = [x for shape in shapes for polyline in shape.polylines for x, _ in polyline]
    ys = [y for shape in shapes for polyline in shape.polylines for _, y in polyline]
    return (min(xs), min(ys), max(xs), max(ys))
