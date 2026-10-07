"""The path the pen will take, in order and with times, for the Plot step's animated preview (spec §5).

EMS calls ad.preview.log_sm_move(ad, move) for every planned move of a preview run. dry_run() lets
a recorder stand in for it, so the path is exactly the one EMS will plot, after its own reordering.
"""
import math
from dataclasses import dataclass

from rosetta.engine.options import PlotSettings, make_axidraw
from rosetta.engine.runner import dry_run, dry_run_estimate
from rosetta.units import MM_PER_INCH

COLLINEAR_MM = 1e-3  # a middle point this close to the line through its neighbours adds nothing
SAME_POINT_MM = 1e-6

Point = tuple[float, float, float]  # x mm, y mm, seconds from the start of the layer


@dataclass(frozen=True)
class Run:
    """Consecutive moves with the pen down (drawing) or up (travelling)."""

    down: bool
    points: list[Point]


@dataclass(frozen=True)
class LayerPlan:
    seconds: float
    pendown_m: float
    runs: list[Run]


class _Recorder:
    def __init__(self):
        self.runs: list[Run] = []
        self.clock_ms = 0.0

    def __call__(self, ad, move) -> None:
        # move = ['SM', (steps2, steps1, duration_ms), (x_in, y_in, pen_up, distance_in, ...)]
        start = (ad.pen.phys.xpos * MM_PER_INCH, ad.pen.phys.ypos * MM_PER_INCH)
        end = (move[2][0] * MM_PER_INCH, move[2][1] * MM_PER_INCH)
        down = not ad.pen.phys.z_up
        started = self.clock_ms / 1000.0
        self.clock_ms += move[1][2]
        point = (end[0], end[1], self.clock_ms / 1000.0)
        last = self.runs[-1] if self.runs else None
        if last is not None and last.down == down and math.dist(last.points[-1][:2], start) <= SAME_POINT_MM:
            last.points.append(point)
        else:
            self.runs.append(Run(down, [(start[0], start[1], started), point]))


def plan_layer(svg_text: str, layer: int, settings: PlotSettings, factory=make_axidraw) -> LayerPlan:
    """Time, pen-down distance and the planned path of one layer. Raises ValueError if the plot
    can't be read. Times are scaled so the path ends at EMS's estimate (pen lifts take time too)."""
    recorder = _Recorder()
    ad = dry_run(svg_text, layer, settings, factory, on_move=recorder)
    result = dry_run_estimate(ad)
    recorded = recorder.clock_ms / 1000.0
    scale = result.seconds / recorded if recorded > 0 else 1.0
    runs = [
        Run(run.down, _simplified([(x, y, t * scale) for x, y, t in run.points]))
        for run in recorder.runs
    ]
    return LayerPlan(result.seconds, result.pendown_m, runs)


def _simplified(points: list[Point]) -> list[Point]:
    """Drop middle points that lie on the straight line between their neighbours.

    EMS splits every straight stroke into many short moves (speeding up, cruising, slowing down);
    the page only needs the corners.
    """
    kept = [points[0]]
    for index in range(1, len(points) - 1):
        (ax, ay, _), (bx, by, _), (cx, cy, _) = kept[-1], points[index], points[index + 1]
        length = math.hypot(cx - ax, cy - ay)
        if length > 0:
            offset = abs((cx - ax) * (ay - by) - (ax - bx) * (cy - ay)) / length
            along = ((bx - ax) * (cx - ax) + (by - ay) * (cy - ay)) / length
            if offset <= COLLINEAR_MM and 0 <= along <= length:
                continue
        kept.append(points[index])
    kept.append(points[-1])
    return kept
