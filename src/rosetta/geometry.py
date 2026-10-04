"""Pure geometry in millimetres.

Rect = (x0, y0, x1, y1) with x0 <= x1 and y0 <= y1. y grows downward on screen, which is
toward the student on the machine (spec §4). Rotation is clockwise as seen on screen.
"""

Point = tuple[float, float]
Rect = tuple[float, float, float, float]


def _rotation(rotation: int) -> int:
    normalized = rotation % 360
    if normalized not in (0, 90, 180, 270):
        raise ValueError("Rotation must be a multiple of 90 degrees.")
    return normalized


def rotated_size(width: float, height: float, rotation: int) -> tuple[float, float]:
    return (height, width) if _rotation(rotation) in (90, 270) else (width, height)


def place_point(
    point: Point,
    art_width: float,
    art_height: float,
    x: float,
    y: float,
    scale: float,
    rotation: int,
    origin: Point,
) -> Point:
    """Artwork point -> machine point. The rotated, scaled artwork box's top-left lands at
    origin + (x, y). origin is the material's corner nearest Home."""
    px, py = point
    turn = _rotation(rotation)
    if turn == 0:
        rx, ry = px, py
    elif turn == 90:
        rx, ry = art_height - py, px
    elif turn == 180:
        rx, ry = art_width - px, art_height - py
    else:
        rx, ry = py, art_width - px
    return (origin[0] + x + rx * scale, origin[1] + y + ry * scale)


def bbox(polylines) -> Rect | None:
    xs = [x for polyline in polylines for x, _ in polyline]
    ys = [y for polyline in polylines for _, y in polyline]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def contains(rect: Rect, point: Point, tolerance: float = 1e-6) -> bool:
    x0, y0, x1, y1 = rect
    x, y = point
    return x0 - tolerance <= x <= x1 + tolerance and y0 - tolerance <= y <= y1 + tolerance


def intersect(a: Rect, b: Rect) -> Rect | None:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x0 >= x1 or y0 >= y1:
        return None
    return (x0, y0, x1, y1)
