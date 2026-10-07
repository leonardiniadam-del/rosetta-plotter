"""Pure geometry in millimetres.

Rect = (x0, y0, x1, y1) with x0 <= x1 and y0 <= y1. y grows downward on screen, which is
toward the student on the machine (spec §4). Rotation is clockwise as seen on screen, by any angle.
"""
import math
from itertools import pairwise

# Imported coordinates carry ~1e-5 mm of float noise; anything this close to an edge counts
# as on it (EMS's own bounds clipping does the same).
EDGE_TOLERANCE_MM = 1e-3
# Shorter than one motor step: a pen dot, not a line.
MIN_RUN_MM = 0.01

Point = tuple[float, float]
Rect = tuple[float, float, float, float]


def _rotation(rotation) -> float:
    """Degrees in [0, 360). ValueError for anything that isn't a finite number."""
    if isinstance(rotation, bool) or not isinstance(rotation, (int, float)) or not math.isfinite(rotation):
        raise ValueError(f"Rotation must be a finite number of degrees: {rotation!r}")
    return float(rotation) % 360.0


def _cos_sin(turn: float) -> tuple[float, float]:
    """Exact for quarter turns, so placements at 0/90/180/270 land on exact numbers."""
    exact = {0.0: (1.0, 0.0), 90.0: (0.0, 1.0), 180.0: (-1.0, 0.0), 270.0: (0.0, -1.0)}.get(turn)
    if exact is not None:
        return exact
    radians = math.radians(turn)
    return math.cos(radians), math.sin(radians)


def rotated_size(width: float, height: float, rotation) -> tuple[float, float]:
    """Size of the upright box around a width x height frame turned by rotation degrees."""
    turn = _rotation(rotation)
    if turn in (90.0, 270.0):
        return (height, width)
    if turn in (0.0, 180.0):
        return (width, height)
    cos, sin = (abs(value) for value in _cos_sin(turn))
    return (width * cos + height * sin, width * sin + height * cos)


def place_point(
    point: Point,
    art_width: float,
    art_height: float,
    x: float,
    y: float,
    scale: float,
    rotation,
    origin: Point,
    scale_y: float | None = None,
) -> Point:
    """Artwork point -> machine point.

    The artwork is scaled on its own axes (scale across its width, scale_y down its height; None means
    the same as scale), turned clockwise by rotation degrees, and the top-left of its upright box lands
    at origin + (x, y). origin is the material's corner nearest Home.
    """
    scale_x, scale_y = scale, scale if scale_y is None else scale_y
    cos, sin = _cos_sin(_rotation(rotation))
    # The linear part: turn(scale(point)). A frame corner lands at (a*u + c*v, b*u + d*v).
    a, b, c, d = cos * scale_x, sin * scale_x, -sin * scale_y, cos * scale_y
    xs = (0.0, a * art_width, a * art_width + c * art_height, c * art_height)
    ys = (0.0, b * art_width, b * art_width + d * art_height, d * art_height)
    px, py = point
    return (
        origin[0] + x + a * px + c * py - min(xs),
        origin[1] + y + b * px + d * py - min(ys),
    )


def bbox(polylines) -> Rect | None:
    xs = [x for polyline in polylines for x, _ in polyline]
    ys = [y for polyline in polylines for _, y in polyline]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def contains(rect: Rect, point: Point, tolerance: float = EDGE_TOLERANCE_MM) -> bool:
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


def _clip_segment(start: Point, end: Point, rect: Rect) -> tuple[Point, Point, bool] | None:
    """Liang–Barsky: the part of segment start->end inside rect, or None.

    Returns (clipped_start, clipped_end, leaves). The endpoints are exactly start / end when
    the segment isn't trimmed there, and leaves is True when the segment exits the rect
    before its end."""
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
    clipped_start = start if t_enter == 0.0 else (x0 + t_enter * dx, y0 + t_enter * dy)
    clipped_end = end if t_exit == 1.0 else (x0 + t_exit * dx, y0 + t_exit * dy)
    return clipped_start, clipped_end, t_exit < 1.0


def _same(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= _SAME and abs(a[1] - b[1]) <= _SAME


def _length(run: list[Point]) -> float:
    return sum(math.dist(a, b) for a, b in pairwise(run))


def clip_polyline(points, rect: Rect) -> list[list[Point]]:
    """Split a polyline into the runs that lie inside rect. Points within EDGE_TOLERANCE_MM
    of an edge count as inside and are clamped onto it; runs shorter than MIN_RUN_MM (dots)
    are dropped."""
    x0, y0, x1, y1 = rect
    inflated = (
        x0 - EDGE_TOLERANCE_MM,
        y0 - EDGE_TOLERANCE_MM,
        x1 + EDGE_TOLERANCE_MM,
        y1 + EDGE_TOLERANCE_MM,
    )
    runs: list[list[Point]] = []
    current: list[Point] = []
    for start, end in pairwise(points):
        piece = _clip_segment(start, end, inflated)
        if piece is None:
            runs.append(current)
            current = []
            continue
        clipped_start, clipped_end, leaves = piece
        if current and _same(current[-1], clipped_start):
            current.append(clipped_end)
        else:
            runs.append(current)
            current = [clipped_start, clipped_end]
        if leaves:
            runs.append(current)
            current = []
    runs.append(current)

    result: list[list[Point]] = []
    for run in runs:
        clamped: list[Point] = []
        for x, y in run:
            point = (min(max(x, x0), x1), min(max(y, y0), y1))
            if not clamped or not _same(clamped[-1], point):
                clamped.append(point)
        if len(clamped) >= 2 and _length(clamped) >= MIN_RUN_MM:
            result.append(clamped)
    return result
