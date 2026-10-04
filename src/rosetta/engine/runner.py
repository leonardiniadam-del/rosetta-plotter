"""Run plots and time estimates through the EMS engine.

Each run uses a fresh EMS AxiDraw object in 'layers' mode (one pen color per run).
Live position is read from EMS internals pinned by tests/test_engine_contract.py.
"""
import threading
from dataclasses import dataclass
from enum import Enum

from lxml import etree

from rosetta.engine.awake import keep_awake
from rosetta.engine.options import PlotSettings, apply_settings, make_axidraw
from rosetta.units import MM_PER_INCH


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


def outcome_for_code(code: int) -> PlotOutcome:
    return _CODES.get(code, PlotOutcome.ERROR)


@dataclass
class PlotResult:
    outcome: PlotOutcome
    resume_svg: str | None  # set when PAUSED or DISCONNECTED
    message: str


@dataclass(frozen=True)
class Progress:
    x_mm: float
    y_mm: float
    pendown_mm: float  # pen-down distance drawn so far in this run


@dataclass(frozen=True)
class Estimate:
    seconds: float
    pendown_m: float


def _clean(svg_text: str) -> str:
    """Drop an XML declaration so plot_setup() can parse the text as a string."""
    text = svg_text.lstrip()
    if text.startswith("<?xml"):
        text = text[text.index("?>") + 2:].lstrip()
    return text


def estimate(svg_text: str, layer: int, settings: PlotSettings, factory=make_axidraw) -> Estimate:
    ad = factory()
    ad.plot_setup(_clean(svg_text))
    apply_settings(ad, settings)
    ad.options.mode = "layers"
    ad.options.layer = layer
    ad.options.preview = True
    ad.options.rendering = 0
    ad.plot_run()
    stats = ad.plot_status.stats
    # down_travel_tot is only filled in when EMS prints its own report; use whichever is set.
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
        """Plot one layer (or resume a paused one). Blocks; call from a worker thread."""
        ad = self._factory()
        ad.plot_setup(_clean(svg_text))
        apply_settings(ad, settings)
        ad.options.preview = preview
        if resume:
            ad.options.mode = "res_plot"
        else:
            ad.options.mode = "layers"
            ad.options.layer = layer
        self._pause = self._event_factory()
        # pyaxidraw's plot_run() installs its own pause event via set_up_pause_receiver();
        # redirect that call to ours (pinned by test_pause_receiver_can_be_redirected).
        install_receiver = ad.set_up_pause_receiver
        ad.set_up_pause_receiver = lambda _ems_event: install_receiver(self._pause)

        done = threading.Event()
        poller = None
        if on_progress is not None:
            poller = threading.Thread(target=self._poll, args=(ad, on_progress, done), daemon=True)
            poller.start()
        try:
            with keep_awake():
                output = ad.plot_run(True)
        except Exception as exc:  # serial errors surface here; report, don't crash the app
            return PlotResult(PlotOutcome.ERROR, None, f"{MESSAGES[PlotOutcome.ERROR]} ({exc})")
        finally:
            done.set()
            if poller is not None:
                poller.join()

        outcome = outcome_for_code(ad.plot_status.stopped)
        keep_resume = outcome in (PlotOutcome.PAUSED, PlotOutcome.DISCONNECTED)
        return PlotResult(outcome, output if keep_resume else None, MESSAGES[outcome])

    def return_home(self, resume_svg: str, settings: PlotSettings) -> str:
        """After a pause, drive the pen back Home. Returns resume data that now starts from Home."""
        ad = self._factory()
        ad.plot_setup(_clean(resume_svg))
        apply_settings(ad, settings)
        ad.options.mode = "res_home"
        return ad.plot_run(True)

    def _poll(self, ad, on_progress, done: threading.Event) -> None:
        while not done.wait(self._poll_interval):
            on_progress(
                Progress(
                    (ad.pen.phys.xpos or 0.0) * MM_PER_INCH,
                    (ad.pen.phys.ypos or 0.0) * MM_PER_INCH,
                    ad.plot_status.stats.down_travel_inch * MM_PER_INCH,
                )
            )


def set_resume_origin_home(resume_svg: str) -> str:
    """After the student slides the pen back Home by hand, make the resume start from Home."""
    root = etree.fromstring(_clean(resume_svg).encode("utf-8"))
    nodes = root.xpath("//*[local-name()='plotdata']")
    if not nodes:
        raise ValueError("No resume data in this plot.")
    nodes[0].set("last_x", "0")
    nodes[0].set("last_y", "0")
    return etree.tostring(root, encoding="unicode")
