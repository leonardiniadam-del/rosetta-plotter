"""Run plots and time estimates through the EMS engine.

Each run uses a fresh EMS AxiDraw object in 'layers' mode (one pen color per run).
Live position is read from EMS internals pinned by tests/test_engine_contract.py.
"""
import dataclasses
import logging
import threading
from dataclasses import dataclass
from enum import Enum

from lxml import etree

from rosetta.engine.awake import keep_awake
from rosetta.engine.options import PlotSettings, apply_settings, make_axidraw
from rosetta.units import MM_PER_INCH

logger = logging.getLogger(__name__)


class PlotOutcome(Enum):
    COMPLETED = "completed"
    PAUSED = "paused"
    DISCONNECTED = "disconnected"
    NOT_CONNECTED = "not_connected"
    ERROR = "error"


# EMS plot_status.stopped after a run (see axidrawinternal/axidraw.py, pause_check).
# 1 and 2 (pause from a "!" layer name, pause between copies) can't happen with
# Rosetta's numbered layers and single copies; they're mapped for completeness.
_CODES = {
    0: PlotOutcome.COMPLETED,
    1: PlotOutcome.PAUSED,
    2: PlotOutcome.PAUSED,
    101: PlotOutcome.NOT_CONNECTED,
    102: PlotOutcome.PAUSED,  # physical pause button
    103: PlotOutcome.PAUSED,  # our software pause
    104: PlotOutcome.DISCONNECTED,
}

MESSAGES = {
    PlotOutcome.COMPLETED: "Plot finished.",
    PlotOutcome.PAUSED: "Plot paused.",
    PlotOutcome.DISCONNECTED: "Plotter disconnected. Plug it back in, slide the pen Home, then resume.",
    PlotOutcome.NOT_CONNECTED: "No plotter found. Plug in the USB cable and the power adapter.",
    PlotOutcome.ERROR: "The plot stopped unexpectedly.",
}

_HOME_MESSAGES = {
    **MESSAGES,
    PlotOutcome.COMPLETED: "The pen is back at Home.",
    PlotOutcome.PAUSED: "Stopped before the pen reached Home.",
}

_NO_PAUSED_PLOT = "There's no paused plot to resume."
_UNREADABLE = "This plot couldn't be read."
_NOT_HOME = "The pen couldn't be moved Home."

_HOME_TOLERANCE_MM = 0.1


def outcome_for_code(code: int) -> PlotOutcome:
    return _CODES.get(code, PlotOutcome.ERROR)


@dataclass
class PlotResult:
    outcome: PlotOutcome
    # The only copy of the paused plot's position. Set when PAUSED or DISCONNECTED, and kept (as
    # given) when a resume or return-Home couldn't run, so the student can try again.
    resume_svg: str | None
    message: str  # plain language, for the student
    details: str = ""  # technical detail, for the app's "Details" link


@dataclass(frozen=True)
class Progress:
    x_mm: float
    y_mm: float
    # pen-down distance drawn so far on this layer (a resumed run starts from the paused distance)
    pendown_mm: float


@dataclass(frozen=True)
class Estimate:
    seconds: float
    pendown_m: float


@dataclass
class _Execution:
    """What one engine run left behind. `error` is set (and `output` isn't) when the engine raised."""

    ad: object | None = None
    output: str | None = None
    error: str | None = None


def _clean(svg_text: str) -> str:
    """Drop an XML declaration so plot_setup() can parse the text as a string."""
    text = svg_text.lstrip()
    if text.startswith("<?xml"):
        text = text[text.index("?>") + 2:].lstrip()
    return text


def _parse(svg_text: str):
    return etree.fromstring(_clean(svg_text).encode("utf-8"), etree.XMLParser(huge_tree=True))


def _plotdata_node(root):
    nodes = root.xpath("//*[local-name()='plotdata']")
    return nodes[0] if nodes else None


def _plotdata(svg_text: str) -> dict | None:
    """The progress data EMS keeps in a plot (layer, pause_dist, last_x ...), or None."""
    try:
        node = _plotdata_node(_parse(svg_text))
    except (etree.XMLSyntaxError, ValueError):
        return None
    return None if node is None else dict(node.attrib)


def _set_plotdata(svg_text: str, **attrs) -> str:
    root = _parse(svg_text)
    node = _plotdata_node(root)
    if node is not None:
        for name, value in attrs.items():
            node.set(name, str(value))
    return etree.tostring(root, encoding="unicode")


def _int_attr(data: dict, name: str, default: int) -> int:
    try:
        return int(data[name])
    except (KeyError, TypeError, ValueError):
        return default


def _paused_plotdata(svg_text: str) -> dict | None:
    """The plotdata of a resumable plot (EMS marks "nothing to resume" with pause_dist < 0)."""
    data = _plotdata(svg_text)
    if data is None or _int_attr(data, "pause_dist", -1) < 0:
        return None
    return data


def _at_home(data: dict) -> bool:
    """Is the pen at Home, going by the plotdata's last_x / last_y?

    EMS keeps those in millimetres in the plot file (inches only inside the engine: plot_status.py
    multiplies by 25.4 when writing and divides when reading), so they compare with the mm tolerance.
    """
    try:
        x_mm, y_mm = float(data["last_x"]), float(data["last_y"])
    except (KeyError, TypeError, ValueError):
        return False
    return abs(x_mm) < _HOME_TOLERANCE_MM and abs(y_mm) < _HOME_TOLERANCE_MM


def _sample(ad) -> Progress:
    return Progress(
        (ad.pen.phys.xpos or 0.0) * MM_PER_INCH,
        (ad.pen.phys.ypos or 0.0) * MM_PER_INCH,
        ad.plot_status.stats.down_travel_inch * MM_PER_INCH,
    )


def estimate(svg_text: str, layer: int, settings: PlotSettings, factory=make_axidraw) -> Estimate:
    """Time and pen-down distance for one layer. Raises ValueError if the plot can't be read."""
    settings = dataclasses.replace(settings)
    try:
        ad = factory()
        ad.plot_setup(_clean(svg_text))
    except Exception as exc:
        logger.exception("Couldn't set up the plot to estimate it")
        raise ValueError(_UNREADABLE) from exc
    apply_settings(ad, settings)
    ad.options.mode = "layers"
    ad.options.layer = layer
    ad.options.preview = True
    ad.options.rendering = 0
    try:
        ad.plot_run()
    except Exception as exc:
        logger.exception("Couldn't estimate the plot")
        raise ValueError(_UNREADABLE) from exc
    if ad.digest is None:  # EMS gave up quietly, e.g. a page without a size in mm or inches
        raise ValueError(_UNREADABLE)
    stats = ad.plot_status.stats
    # EMS fills down_travel_tot in its report; down_travel_inch is the fallback.
    pendown_in = max(stats.down_travel_tot, stats.down_travel_inch)
    return Estimate(stats.pt_estimate / 1000.0, pendown_in * MM_PER_INCH / 1000.0)


class PlotRunner:
    def __init__(self, factory=make_axidraw, poll_interval: float = 0.1, event_factory=threading.Event):
        self._factory = factory
        self._poll_interval = poll_interval
        self._event_factory = event_factory
        self._pause = event_factory()

    def pause(self) -> None:
        """Ask the current run to pause. Safe to call from any thread."""
        self._pause.set()

    def run(
        self,
        svg_text: str,
        layer: int,
        settings: PlotSettings,
        on_progress=None,
        resume: bool = False,
        preview: bool = False,
    ) -> PlotResult:
        """Plot one layer (or resume a paused one). Blocks; call from a worker thread.

        When resuming, the layer to finish is the one the paused plot recorded; `layer` is used
        only if that record says "every layer".
        """
        settings = dataclasses.replace(settings)
        self._pause = self._event_factory()  # first, so a Pause pressed during setup still counts
        keep = None  # what the student is left holding if this run can't draw anything
        layer_to_keep = layer
        if resume:
            data = _paused_plotdata(svg_text)
            if data is None:
                return PlotResult(PlotOutcome.ERROR, svg_text, _NO_PAUSED_PLOT)
            if _int_attr(data, "layer", -2) < 0:
                svg_text = _set_plotdata(svg_text, layer=layer)  # "every layer" would redraw the others
            else:
                layer_to_keep = _int_attr(data, "layer", layer)
            keep = svg_text

        def configure(options):
            if resume:
                options.mode = "res_plot"
            else:
                options.mode = "layers"
                options.layer = layer

        execution = self._execute(svg_text, settings, configure, preview, on_progress)
        if execution.error is not None:
            failed = MESSAGES[PlotOutcome.ERROR]
            return PlotResult(PlotOutcome.ERROR, keep, failed, details=execution.error)
        ad = execution.ad
        stopped = ad.plot_status.stopped
        if stopped == 0 and ad.digest is None:  # EMS gave up quietly: nothing was read, nothing drawn
            return PlotResult(PlotOutcome.ERROR, keep, _UNREADABLE)

        outcome = outcome_for_code(stopped)
        if outcome in (PlotOutcome.PAUSED, PlotOutcome.DISCONNECTED):
            # A stop during the final trip Home happens after EMS has reset the layer to "every
            # layer", which would redraw the other pens' work on resume. Put our layer back.
            resume_svg = _set_plotdata(execution.output, layer=layer_to_keep)
        elif outcome is PlotOutcome.COMPLETED:
            resume_svg = None
        else:  # NOT_CONNECTED or ERROR: nothing was drawn, so the old resume data is still the truth
            resume_svg = keep
        return PlotResult(outcome, resume_svg, MESSAGES[outcome])

    def return_home(self, resume_svg: str, settings: PlotSettings, preview: bool = False) -> PlotResult:
        """After a pause, drive the pen back Home. The result's resume_svg then starts from Home."""
        settings = dataclasses.replace(settings)
        self._pause = self._event_factory()
        if _paused_plotdata(resume_svg) is None:
            return PlotResult(PlotOutcome.ERROR, resume_svg, _NO_PAUSED_PLOT)

        def configure(options):
            options.mode = "res_home"

        execution = self._execute(resume_svg, settings, configure, preview, None)
        if execution.error is not None:
            failed = MESSAGES[PlotOutcome.ERROR]
            return PlotResult(PlotOutcome.ERROR, resume_svg, failed, details=execution.error)

        outcome = outcome_for_code(execution.ad.plot_status.stopped)
        message = _HOME_MESSAGES[outcome]
        if outcome is PlotOutcome.COMPLETED:
            data = _plotdata(execution.output)
            if data is None or not _at_home(data):  # EMS gave up quietly without moving the pen
                return PlotResult(PlotOutcome.ERROR, resume_svg, _NOT_HOME)
            return PlotResult(outcome, execution.output, message)
        if outcome in (PlotOutcome.PAUSED, PlotOutcome.DISCONNECTED):
            # Stopped partway: EMS recorded where the pen is now.
            return PlotResult(outcome, execution.output, message)
        return PlotResult(outcome, resume_svg, message)

    def _execute(
        self, svg_text: str, settings: PlotSettings, configure, preview: bool, on_progress
    ) -> _Execution:
        """Shared plumbing for a non-estimate engine run. Always leaves the plotter's port closed."""
        ad = None
        poller = None
        done = threading.Event()
        try:
            ad = self._factory()
            ad.plot_setup(_clean(svg_text))
            apply_settings(ad, settings)
            ad.options.preview = preview
            ad.options.rendering = 0  # Rosetta draws its own preview; EMS needn't build one
            configure(ad.options)
            # pyaxidraw's plot_run() installs its own pause event via set_up_pause_receiver();
            # redirect that call to ours (pinned by test_pause_receiver_can_be_redirected).
            pause = self._pause
            install_receiver = ad.set_up_pause_receiver
            ad.set_up_pause_receiver = lambda _ems_event: install_receiver(pause)
            if on_progress is not None:
                poller = threading.Thread(target=self._poll, args=(ad, on_progress, done), daemon=True)
                poller.start()
            with keep_awake():
                output = ad.plot_run(True)
            done.set()
            if poller is not None:
                poller.join(timeout=2)
                poller = None
                self._final_sample(ad, on_progress)
            return _Execution(ad, output)
        except Exception as exc:  # serial errors surface here; report, don't crash the app
            logger.exception("The plot run failed")
            if ad is not None:
                try:
                    ad.pen.pen_raise(ad)  # don't leave the pen resting on the paper
                except Exception:
                    logger.debug("Couldn't raise the pen after the failure", exc_info=True)
            return _Execution(ad, error=f"{type(exc).__name__}: {exc}")
        finally:
            done.set()
            if poller is not None:
                poller.join(timeout=2)
            if ad is not None:
                ad.__dict__.pop("set_up_pause_receiver", None)  # the lambda points back at ad
                try:
                    # EMS leaves a port it didn't open alone, and an open port blocks reconnecting.
                    ad.disconnect()
                except Exception:
                    logger.exception("Couldn't close the plotter's serial port")

    def _poll(self, ad, on_progress, done: threading.Event) -> None:
        failed = False
        while not done.wait(self._poll_interval):
            try:
                on_progress(_sample(ad))
            except Exception:
                if not failed:  # one traceback is enough; a broken callback tends to fail every time
                    logger.exception("The progress callback failed; still plotting")
                    failed = True

    @staticmethod
    def _final_sample(ad, on_progress) -> None:
        try:
            on_progress(_sample(ad))
        except Exception:
            logger.exception("The progress callback failed")


def paused_layer(resume_svg: str) -> int | None:
    """The layer a saved paused plot will finish, or None if it holds no resumable plot or the
    layer isn't recorded (EMS's "every layer")."""
    data = _paused_plotdata(resume_svg)
    if data is None:
        return None
    layer = _int_attr(data, "layer", -2)
    return layer if layer >= 1 else None


def set_resume_origin_home(resume_svg: str) -> str:
    """After the student slides the pen back Home by hand, make the resume start from Home."""
    if _plotdata(resume_svg) is None:
        raise ValueError("No resume data in this plot.")
    return _set_plotdata(resume_svg, last_x="0", last_y="0")
