"""Step 5, Plot (spec §5, §7, §10): prepare the job, trace it, and plot it one pen color at a time,
through pen changes, pauses, lost cables and re-homing.

Each state change goes to the page as a "plot_state" event (the status() dict); the pen's live position
as "plot_progress". Engine runs happen on a worker thread, so the page's buttons return at once.
From plan2-notes.md: never estimate while plotting; a pause asked for before a run listens is asked
again; any mid-run error means the pen's position is unknown; a resume uses the settings its plot
started with; the progress callback never blocks.
"""
import logging
import threading
from dataclasses import dataclass

from rosetta.app.machine import NO_POWER
from rosetta.engine.options import PlotSettings
from rosetta.engine.preview import Run, plan_layer
from rosetta.engine.runner import PlotOutcome, PlotResult, PlotRunner, set_resume_origin_home
from rosetta.errors import UserProblem
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg

logger = logging.getLogger(__name__)

MANY_COLORS = 10  # from this many pens, say how many pen changes are coming
MAX_COLORS = 1000  # EMS plots layers 1-1000
WORKER_JOIN_S = 30.0

NOTHING_TO_PLOT = "Nothing to plot: no lines land on the paper."
TOO_MANY_COLORS = ("This drawing has more than 1000 colors. Reduce the colors in your design app, "
                   "then import it again.")
FINISH_FIRST = "Finish or cancel the current plot first."
PREPARE_FIRST = "Wait a moment: the plot is still being prepared."  # the page prepares it whenever it's idle
STILL_PREPARING = "The plot is still being prepared. Wait a moment, then try again."
CHANGED_WHILE_PREPARING = "Something changed while the plot was being prepared, so it's being prepared again."
NOT_NOW = "That can't be done right now."
CLIPPED = "Some lines hang off the paper or out of the plotter's reach. Those parts won't be drawn."
DONE = "Done! The pen is back Home."
SLIDE_HOME = ("Slide the pen to the corner next to the HOME label and the USB port, "
              "then click It's in the corner.")
HOME_UNKNOWN = "Slide the pen Home before the next plot."
UNEXPECTED = "The plot stopped unexpectedly."
CHECK_CABLE = "Check the USB cable and the power adapter, then click Continue."

ACTIONS = {
    "idle": [],
    "ready": ["trace", "start"],
    "tracing": ["stop"],
    "load_pen": ["continue", "cancel"],
    "plotting": ["pause"],
    "pausing": [],
    "paused": ["resume", "home", "cancel"],
    "homing": ["pause"],
    "paused_at_home": ["resume", "cancel"],
    "reconnect": ["reconnect", "cancel"],
    "slide_home": ["rehomed", "cancel"],
    "not_connected": ["retry", "cancel"],
    "done": ["start", "trace"],
}
_AT_REST = ("idle", "ready", "done")


@dataclass(frozen=True)
class Layer:
    number: int  # the plot SVG's layer, from 1
    color: str
    name: str
    seconds: float
    pendown_mm: float
    runs: list[Run]


@dataclass(frozen=True)
class Prepared:
    svg: str
    layers: list[Layer]
    ink_bbox: tuple[float, float, float, float]
    warnings: list[str]


class PlotController:
    def __init__(self, machine, session, sink, runner_factory=PlotRunner, planner=plan_layer):
        self._machine = machine
        self._session = session
        self._sink = sink
        self._runner = runner_factory()
        self._plan = planner
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._prepared: Prepared | None = None
        self._state = "idle"
        self._message = ""
        self._details = ""
        self._index = 0  # the layer being plotted (0-based)
        self._settings: PlotSettings | None = None  # what this plot started with; its resume uses them too
        self._resume_svg: str | None = None
        self._at_home = True  # is the pen known to be at Home?
        self._was_at_home = True  # ...before the current run (a run that never connected moved nothing)
        self._retry_resume = False
        self._pause_wanted = False
        self._preparing = False  # prepare() is composing and planning, outside the lock
        self._stale = False  # something changed mid-plot (or mid-prepare): the prepared plot is out of date

    # What the page sees.

    def status(self) -> dict:
        prepared, index = self._prepared, self._index
        layer = prepared.layers[index] if prepared and index < len(prepared.layers) else None
        return {
            "state": self._state,
            "actions": list(ACTIONS[self._state]),
            "layer": index,
            "layers": len(prepared.layers) if prepared else 0,
            "color": layer.color if layer else None,
            "name": layer.name if layer else None,
            "message": self._message,
            "details": self._details,
        }

    def busy(self) -> bool:
        """Is a plot (or a trace) under way? Closing the app then needs asking first."""
        return self._state not in _AT_REST

    def summary(self) -> dict:
        """The prepared plot: per-pen times, warnings, and the planned path to animate."""
        prepared = self._prepared
        if prepared is None:
            raise UserProblem(PREPARE_FIRST)
        return self._summary(prepared)

    @staticmethod
    def _summary(prepared: Prepared) -> dict:
        return {
            "layers": [
                {
                    "layer": layer.number,
                    "color": layer.color,
                    "name": layer.name,
                    "seconds": round(layer.seconds, 1),
                    "pendown_mm": round(layer.pendown_mm, 1),
                    "path": [
                        {"down": run.down, "points": [round(value, 2) for point in run.points for value in point]}
                        for run in layer.runs
                    ],
                }
                for layer in prepared.layers
            ],
            "total_seconds": round(sum(layer.seconds for layer in prepared.layers), 1),
            "ink_bbox": list(prepared.ink_bbox),
            "warnings": list(prepared.warnings),
        }

    # Getting ready.

    def prepare(self) -> dict:
        """Compose the job and plan every layer: slow for big drawings, so the page awaits it with a
        spinner. Refused while a plot is under way (an estimate's CPU load would fight its timing) or
        another prepare is running; Start and Trace wait for it too. If something changes meanwhile,
        it fails and the plot goes back to idle, to be prepared again."""
        with self._lock:
            if self._preparing:
                raise UserProblem(STILL_PREPARING)
            if self._state not in _AT_REST:
                raise UserProblem(FINISH_FIRST)
            self._preparing, self._stale = True, False
        try:
            prepared = self._plan_job()
        except BaseException:
            with self._lock:
                self._preparing = False
            raise
        with self._lock:
            self._preparing = False
            if self._stale:
                self._stale = False
                self._set("idle")  # tells the page to prepare the plot again
                raise UserProblem(CHANGED_WHILE_PREPARING)
            self._prepared = prepared
            self._index = 0
            self._set("ready")
        return self._summary(prepared)

    def invalidate(self) -> None:
        """The drawing, paper, pen or plotter changed, so the prepared plot is out of date. A running
        plot or trace keeps its own copy: the change is remembered, and the prepared plot is dropped
        once it's over. A prepare under way fails instead (see prepare)."""
        with self._lock:
            if self._preparing or self._state not in _AT_REST:
                self._stale = True
            if self._state in _AT_REST:
                self._prepared = None
                self._index = 0
                if self._state != "idle":
                    self._set("idle")

    def trace(self) -> dict:
        """Pen up around everything that will be drawn, then Home. Blocks until done; Stop ends it."""
        with self._lock:
            self._need_prepared()
            box = self._prepared.ink_bbox
            self._set("tracing")
        try:
            return self._machine.trace(box)
        finally:
            with self._lock:
                self._rest("ready")

    # Plotting.

    def start(self) -> None:
        """Start the prepared plot (also "Plot another copy"). The pen goes Home and the plot takes over
        the USB port; with several pens, the first one is asked for before anything is drawn."""
        with self._lock:
            self._need_prepared()
            self._settings = self._machine.release_for_plot()  # checks power, returns Home; may refuse
            self._index = 0
            self._resume_svg = None
            self._at_home = True
            if len(self._prepared.layers) > 1:
                self._ask_for_pen()
            else:
                self._run_layer(resume=False)

    def continue_pen(self) -> None:
        """The student has put the asked-for pen in the holder."""
        with self._lock:
            self._expect("load_pen")
            self._check_power()
            self._run_layer(resume=False)

    def pause(self) -> None:
        """Pause at the next step, pen up. A late click after the run has ended does nothing."""
        with self._lock:
            if self._state not in ("plotting", "homing"):
                return
            self._pause_wanted = True
            self._runner.pause()
            if self._state == "plotting":
                self._set("pausing", "Pausing...")

    def resume(self) -> None:
        with self._lock:
            self._expect("paused", "paused_at_home")
            self._check_power()
            self._run_layer(resume=True)

    def home(self) -> None:
        """While paused: send the pen Home (to check or swap it). Resume then carries on from there."""
        with self._lock:
            self._expect("paused")
            self._check_power()
            svg, settings, runner = self._resume_svg, self._settings, self._runner
            self._begin_run()
            self._set("homing", "Sending the pen Home.")
            self._start_worker(lambda: runner.return_home(svg, settings), self._after_home)

    def cancel(self) -> None:
        """Stop the plot for good. If the pen isn't known to be Home, the motors go off for re-homing."""
        with self._lock:
            self._expect("load_pen", "paused", "paused_at_home", "reconnect", "slide_home", "not_connected")
            self._end_plot("Plot cancelled.")

    def reconnect(self) -> None:
        """After a lost cable or an error: once the plotter answers, free its carriage for a slide Home."""
        with self._lock:
            self._expect("reconnect")
            if self._machine.release_motors():
                self._set("slide_home", SLIDE_HOME)
            else:
                self._set("reconnect", f"Still no plotter found. {CHECK_CABLE}")

    def rehomed(self) -> None:
        """The student slid the pen Home, so the paused plot resumes from there (spec §10)."""
        with self._lock:
            self._expect("slide_home")
            self._resume_svg = set_resume_origin_home(self._resume_svg)
            self._at_home = True
            self._set("paused_at_home", "The pen is Home. Click Resume to carry on.")

    def retry(self) -> None:
        """Try the run again after it couldn't find the plotter (nothing moved)."""
        with self._lock:
            self._expect("not_connected")
            self._check_power()
            self._run_layer(resume=self._retry_resume)

    def shutdown(self) -> None:
        """The app is closing: pause a running plot (pen up) and wait for the engine to let go."""
        with self._lock:
            if self._state in ("plotting", "homing"):
                self._pause_wanted = True
                self._runner.pause()
            worker = self._worker
        if worker is not None:
            worker.join(WORKER_JOIN_S)

    # Inside.

    def _set(self, state: str, message: str = "", details: str = "") -> None:
        self._state, self._message, self._details = state, message, details
        self._sink.emit("plot_state", self.status())

    def _rest(self, state: str, message: str = "", details: str = "") -> None:
        """Back at rest, "ready" or "done". If something changed meanwhile, the prepared plot is out of
        date: drop it and go to idle instead (keeping the message), and the page prepares it again."""
        if self._stale:
            self._stale = False
            self._prepared = None
            self._index = 0
            state = "idle"
        self._set(state, message, details)

    def _expect(self, *states: str) -> None:
        if self._state not in states:
            raise UserProblem(NOT_NOW)

    def _need_prepared(self) -> None:
        if self._preparing:
            raise UserProblem(STILL_PREPARING)
        if self._state not in ("ready", "done") or self._prepared is None:
            raise UserProblem(PREPARE_FIRST if self._state in _AT_REST else FINISH_FIRST)

    def _check_power(self) -> None:
        """Before every run, not only at Start (spec §10). If the plotter can't be reached, the run
        itself says so."""
        if self._machine.power_ok_for_plot() is False:
            raise UserProblem(NO_POWER)

    def _plan_job(self) -> Prepared:
        settings = self._machine.plot_settings()
        model = get_model(settings.model)
        job = self._session.compose(model)
        if not job.groups:
            raise UserProblem(NOTHING_TO_PLOT)
        if len(job.groups) > MAX_COLORS:
            raise UserProblem(TOO_MANY_COLORS)
        svg = plot_svg(model, job.groups)
        layers = []
        for number, group in enumerate(job.groups, start=1):
            plan = self._plan(svg, number, settings)
            layers.append(Layer(number, group.color, group.name, plan.seconds, plan.pendown_m * 1000, plan.runs))
        return Prepared(svg, layers, job.ink_bbox, self._warnings(job.clipped, len(layers)))

    def _warnings(self, clipped: bool, colors: int) -> list[str]:
        warnings = []
        for piece in list(self._session.pieces):
            for issue in piece.artwork.issues:
                if issue.code == "white" and not self._session.skip_white:
                    continue  # the student chose to draw white shapes after all
                if issue.message not in warnings:
                    warnings.append(issue.message)
        if clipped:
            warnings.append(CLIPPED)
        if colors >= MANY_COLORS:
            warnings.append(f"This drawing uses {colors} pen colors, so you'll change pens {colors - 1} times.")
        return warnings

    def _ask_for_pen(self) -> None:
        layer = self._prepared.layers[self._index]
        count = len(self._prepared.layers)
        self._set(
            "load_pen",
            f"Put the {layer.name} pen in the holder ({self._index + 1} of {count}), then click Continue.",
        )

    def _run_layer(self, resume: bool) -> None:
        layer = self._prepared.layers[self._index]
        svg = self._resume_svg if resume else self._prepared.svg
        settings, runner = self._settings, self._runner
        self._retry_resume = resume
        self._begin_run()
        self._set("plotting", f"Plotting the {layer.name} pen ({self._index + 1} of {len(self._prepared.layers)}).")
        self._start_worker(
            lambda: runner.run(svg, layer.number, settings, on_progress=self._on_progress, resume=resume),
            self._after_run,
        )

    def _begin_run(self) -> None:
        self._was_at_home, self._at_home = self._at_home, False
        self._pause_wanted = False

    def _start_worker(self, work, then) -> None:
        def target():
            try:
                result = work()
            except Exception as error:  # PlotRunner reports problems as results; this would be a bug
                logger.exception("The plot worker failed")
                result = PlotResult(PlotOutcome.ERROR, None, UNEXPECTED, details=f"{type(error).__name__}: {error}")
            with self._lock:
                try:
                    then(result)
                except Exception:
                    logger.exception("Couldn't finish handling the plot run")
                    self._give_up()

        self._worker = threading.Thread(target=target, name="rosetta-plot", daemon=True)
        self._worker.start()

    def _after_run(self, result: PlotResult) -> None:
        if result.resume_svg is not None:
            self._resume_svg = result.resume_svg
        outcome = result.outcome
        if outcome is PlotOutcome.COMPLETED:
            self._resume_svg = None
            self._at_home = True  # every layer run ends at Home
            self._index += 1
            if self._index < len(self._prepared.layers):
                self._ask_for_pen()
            else:
                self._machine.after_plot(at_home=True)
                self._index = 0
                self._rest("done", DONE)
        elif outcome is PlotOutcome.PAUSED:
            self._set("paused", "Paused. The pen is up.")
        elif outcome is PlotOutcome.NOT_CONNECTED:
            self._at_home = self._was_at_home  # the run never started, so nothing moved
            self._set("not_connected", result.message)
        else:  # DISCONNECTED or ERROR
            self._lost(result)

    def _after_home(self, result: PlotResult) -> None:
        if result.resume_svg is not None:
            self._resume_svg = result.resume_svg
        outcome = result.outcome
        if outcome is PlotOutcome.COMPLETED:
            self._at_home = True
            self._set("paused_at_home", "The pen is Home. Check or swap it, then click Resume.")
        elif outcome is PlotOutcome.PAUSED:
            self._set("paused", result.message)
        elif outcome is PlotOutcome.NOT_CONNECTED:
            self._at_home = self._was_at_home
            self._set("paused", result.message)
        else:
            self._lost(result)

    def _lost(self, result: PlotResult) -> None:
        """A pulled cable or an engine error: the pen may be anywhere (plan2-notes.md). With progress to
        come back to, ask for the cable and then a slide Home before resuming; otherwise end the plot."""
        if self._resume_svg is None:
            self._end_plot(result.message, result.details)
            return
        if result.outcome is PlotOutcome.DISCONNECTED:
            message = "Plotter disconnected. Plug it back in, then click Continue."
        else:
            message = f"{result.message} {CHECK_CABLE}"
        self._set("reconnect", message, result.details)

    def _give_up(self) -> None:
        """Handling a run's end failed (a bug). With progress to come back to, ask for the cable and a
        slide Home, as after a lost cable. Otherwise end the plot and let go of the plotter, so it never
        stays "plotting" (Step 1 then finds it again)."""
        if self._resume_svg is not None:
            self._set("reconnect", f"{UNEXPECTED} {CHECK_CABLE}")
            return
        try:
            self._machine.abandon_plot()
        except Exception:
            logger.exception("Couldn't let go of the plotter")
        self._index = 0
        self._rest("ready", UNEXPECTED)

    def _end_plot(self, message: str, details: str = "") -> None:
        """Give the plotter back and drop the plot's progress. The prepared plot stays for a new start.
        If the plotter can't be given back, the plot is left as it was, so nothing is lost."""
        at_home = self._at_home
        self._machine.after_plot(at_home=at_home)
        self._resume_svg = None
        self._index = 0
        if not at_home:
            message = f"{message} {HOME_UNKNOWN}"
        self._rest("ready", message, details)

    def _on_progress(self, progress) -> None:
        """Called on the engine's poller thread every 100 ms: never blocks, never takes the lock."""
        if self._pause_wanted:
            self._runner.pause()  # a pause asked for before this run's pause event existed
        prepared, index = self._prepared, self._index
        if prepared is None or index >= len(prepared.layers):
            return
        layer = prepared.layers[index]
        fraction = min(1.0, progress.pendown_mm / layer.pendown_mm) if layer.pendown_mm > 0 else 1.0
        later = sum(other.seconds for other in prepared.layers[index + 1:])
        self._sink.emit("plot_progress", {
            "layer": index,
            "x": round(progress.x_mm, 2),
            "y": round(progress.y_mm, 2),
            "pendown_mm": round(progress.pendown_mm, 1),
            "fraction": round(fraction, 4),
            "seconds_left": round(layer.seconds * (1 - fraction) + later, 1),
        })
