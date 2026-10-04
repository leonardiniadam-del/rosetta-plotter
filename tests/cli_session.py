"""A scripted terminal for the rosetta-plot CLI.

Session.run(argv) calls rosetta.cli.main with:
  * input() answered from a script (an answer may also be an exception to raise, like Ctrl+C at a prompt),
  * every plotter the CLI opens being a real EMS engine talking to a fake EBB (tests/fake_ebb.py),
  * a "Ctrl+C" you can press from inside a plot (press_ctrl_c_at),
  * everything the CLI prints, and every prompt and answer, collected in session.output.
No test here can touch a real plotter: EMS's port search is switched off.
"""
import _thread
import builtins
import contextlib
import io
import json
import threading
from collections import namedtuple
from pathlib import Path

import pytest
from lxml import etree
from plotink import ebb_serial
from pyaxidraw import axidraw

from rosetta import cli
from rosetta.engine.plotter import Plotter
from rosetta.engine.runner import PlotRunner
from tests.fake_ebb import FakeEBB, IFakeEBB, layered_svg, skip_engine_waits

LAYER_NAMES = ["black", "red", "blue", "green"]
LAYER_COLORS = ["#000000", "#ff0000", "#0000ff", "#00aa00"]

# On layered_svg() layer 1 the pen is down for the first stroke between moves 11 and 17.
MID_STROKE = 14


def make_plot(folder: Path, layers: int = 2, model: int = 1) -> Path:
    """Write folder/plot.svg and plot.json like `rosetta-plot prepare`; returns the .svg path."""
    plot = folder / "plot"
    plot.with_suffix(".svg").write_text(layered_svg(layers=layers), encoding="utf-8")
    meta = {
        "model": model,
        "layers": [
            {"layer": number, "color": LAYER_COLORS[number - 1], "name": LAYER_NAMES[number - 1]}
            for number in range(1, layers + 1)
        ],
        "ink_bbox": [20.0, 23.0, 200.0, 125.0],
        "clipped": False,
    }
    plot.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    return plot.with_suffix(".svg")


def new_plotter_ebb(nickname="Lab m1p1", **kw) -> IFakeEBB:
    return IFakeEBB(nickname=nickname, move_sleep=0, **kw)


class EngineCall(namedtuple("EngineCall", "kind layer svg")):
    """One request to the engine: kind is "run", "resume" or "home"; svg is what it was given."""

    @property
    def origin(self) -> tuple[float, float]:
        """Where the plotdata in svg says the pen is (mm from Home)."""
        return paused_origin(self.svg)


def paused_origin(svg_text: str) -> tuple[float, float]:
    node = etree.fromstring(svg_text.encode("utf-8")).xpath("//*[local-name()='plotdata']")[0]
    return (float(node.get("last_x")), float(node.get("last_y")))


class Session:
    """One run of the CLI.

    answers          what the person types at each prompt, in order; an exception instance is raised
                     instead of returned (KeyboardInterrupt() = Ctrl+C at that prompt)
    runner_ebbs      the fake EBB for each successive engine run (one plot run, resume or return-Home);
                     None = no plotter plugged in for that run; an exception instance = the engine
                     raises it; runs past the end get a fresh FakeEBB
    plotter          the fake EBB behind every interactive Plotter the CLI opens (pre-flight, release
                     motors, trace, pen, identify); defaults to one named "Lab m1p1"
    no_plotter       True = interactive connects always fail
    connect_failures how many of the next interactive connects fail (settable while running)
    """

    def __init__(self, answers=(), runner_ebbs=(), plotter=None, no_plotter=False, connect_failures=0):
        self.answers = list(answers)
        self.runner_ebbs = list(runner_ebbs)
        self.plotter = plotter if plotter is not None else new_plotter_ebb()
        self.no_plotter = no_plotter
        self.connect_failures = connect_failures
        self.engine_ebbs = []  # the EBB each engine run actually used (None = no plotter)
        self.calls = []  # what the CLI asked the engine for, as EngineCall(kind, layer, svg)
        self.interrupt_inside_pause = False  # the next pause request first gets another Ctrl+C...
        self.pause_failures = 0  # ...and this many pause requests fail with a Ctrl+C before one works
        self.runners = []
        self.prompts = []
        self.output = ""
        self.rc = None
        self._hooks = []  # [substring, callable, once]
        self._pause_requested = threading.Event()
        self._out = None

    @property
    def runs(self) -> int:
        return len(self.engine_ebbs)

    def when_prompted(self, text, action, once=True):
        """Call action(session) when a prompt containing text is shown (before it is answered)."""
        self._hooks.append([text, action, once])

    def press_ctrl_c_at(self, ebb, move, presses=1):
        """From `ebb`'s move number `move`, press Ctrl+C in the main thread (`presses` times, on
        consecutive moves, like a held key repeating), then hold the fake plotter still until the CLI
        has asked the engine to pause (a person's slow reaction)."""
        last = move + presses - 1

        def on_sm(count):
            if move <= count <= last:
                _thread.interrupt_main()
            if count == last:
                self._pause_requested.wait(5)

        ebb.on_sm = on_sm

    # What the CLI sees instead of the real thing.

    def _input(self, prompt=""):
        self.prompts.append(prompt)
        for hook in list(self._hooks):
            if hook[0] in prompt:
                if hook[2]:
                    self._hooks.remove(hook)
                hook[1](self)
        if not self.answers:
            raise AssertionError(f"the script ran out of answers at the prompt: {prompt!r}")
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException) or (isinstance(answer, type) and issubclass(answer, BaseException)):
            print(prompt)
            raise answer
        print(f"{prompt}{answer}")
        return answer

    def _make_plotter(self, *args, **kwargs):
        session = self

        class FakeInteractiveAxiDraw(axidraw.AxiDraw):
            def connect(self):
                if session.no_plotter:
                    return False
                if session.connect_failures > 0:
                    session.connect_failures -= 1
                    return False
                self.options.port = session.plotter  # EMS then uses this "port", not a real one
                return super().connect()

        plotter = Plotter(factory=lambda: FakeInteractiveAxiDraw(user_message_fun=lambda text: None))
        real_request_pause = plotter.request_pause

        def request_pause():
            session._pause_requested.set()
            real_request_pause()

        plotter.request_pause = request_pause
        return plotter

    def _make_runner(self, *args, **kwargs):
        session = self

        class FakeAxiDraw(axidraw.AxiDraw):
            def plot_run(self, output=False):
                if isinstance(self.rosetta_ebb, BaseException):
                    raise self.rosetta_ebb  # the engine itself blows up
                self.options.port = self.rosetta_ebb  # None: EMS looks for a plotter, finds none
                return super().plot_run(output)

        def make():
            index = len(session.engine_ebbs)
            ebb = session.runner_ebbs[index] if index < len(session.runner_ebbs) else FakeEBB()
            session.engine_ebbs.append(ebb)
            session._pause_requested.clear()
            ad = FakeAxiDraw(user_message_fun=lambda text: None)
            ad.rosetta_ebb = ebb
            return ad

        runner = PlotRunner(factory=make)
        real_pause, real_run, real_return_home = runner.pause, runner.run, runner.return_home

        def pause():
            if session.interrupt_inside_pause:
                session.interrupt_inside_pause = False
                _thread.interrupt_main()  # another Ctrl+C lands while the pause is being requested
            if session.pause_failures > 0:
                session.pause_failures -= 1
                raise KeyboardInterrupt  # ...or even takes the pause request down with it
            real_pause()
            session._pause_requested.set()

        def run(svg_text, layer, settings, *args, **kwargs):
            session.calls.append(EngineCall("resume" if kwargs.get("resume") else "run", layer, svg_text))
            return real_run(svg_text, layer, settings, *args, **kwargs)

        def return_home(resume_svg, settings, *args, **kwargs):
            session.calls.append(EngineCall("home", None, resume_svg))
            return real_return_home(resume_svg, settings, *args, **kwargs)

        runner.pause, runner.run, runner.return_home = pause, run, return_home
        self.runners.append(runner)
        return runner

    def run(self, argv) -> int:
        """Run `rosetta-plot <argv>`; the exit code. Anything the CLI doesn't catch propagates."""
        self._out = io.StringIO()
        with pytest.MonkeyPatch.context() as patch:
            skip_engine_waits(patch)
            patch.setattr(ebb_serial, "openPort", lambda: None)  # never touch a real plotter
            patch.setattr(builtins, "input", self._input)
            patch.setattr(cli, "Plotter", self._make_plotter)
            patch.setattr(cli, "PlotRunner", self._make_runner)
            with contextlib.redirect_stdout(self._out):
                try:
                    self.rc = cli.main([str(part) for part in argv])
                except KeyboardInterrupt as stray:  # as a traceback it would also abort the whole test run
                    raise AssertionError("Ctrl+C got out of rosetta-plot as an exception") from stray
                finally:
                    self.output = self._out.getvalue()
        return self.rc

    # Things the tests ask afterwards.

    def pen_commands(self, ebb):
        return [command for command, _move in ebb.pen_cmds]

    def drew(self, ebb) -> bool:
        return "down" in self.pen_commands(ebb)

    def times_asked(self, text) -> int:
        return sum(1 for prompt in self.prompts if text in prompt)
