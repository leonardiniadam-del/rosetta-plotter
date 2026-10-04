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


_SAME = 1e-9


def _clip_segment(start: Point, end: Point, rect: Rect) -> tuple[Point, Point] | None:
    """Liang–Barsky: the part of segment start->end inside rect, or None."""
    x0, y0 = start
    dx, dy = end[0] - x0, end[1] - y0
    t_enter, t_exit = 0.0, 1.0
    for p, q in ((-dx, x0 - rect[0]), (dx, rect[2] - x0), (-dy, y0 - rect[1]), (dy, rect[3] - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            if t > t_exit:
                return None
            t_enter = max(t_enter, t)
        else:
            if t < t_enter:
                return None
            t_exit = min(t_exit, t)
    return (x0 + t_enter * dx, y0 + t_enter * dy), (x0 + t_exit * dx, y0 + t_exit * dy)


def _same(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= _SAME and abs(a[1] - b[1]) <= _SAME


def clip_polyline(points, rect: Rect) -> list[list[Point]]:
    """Split a polyline into the runs that lie inside rect."""
    runs: list[list[Point]] = []
    current: list[Point] = []
    for start, end in zip(points, points[1:]):
        piece = _clip_segment(start, end, rect)
        if piece is None:
            if len(current) >= 2:
                runs.append(current)
            current = []
            continue
        clipped_start, clipped_end = piece
        if current and _same(current[-1], clipped_start):
            current.append(clipped_end)
        else:
            if len(current) >= 2:
                runs.append(current)
            current = [clipped_start, clipped_end]
        if not _same(clipped_end, end):  # the segment leaves the rect here
            runs.append(current)
            current = []
    if len(current) >= 2:
        runs.append(current)
    return runs
