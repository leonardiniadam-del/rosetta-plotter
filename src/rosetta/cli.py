"""rosetta-plot: command-line access to the Rosetta core, for testing on real plotters.

Students use the app (Plan 2). This tool exists so plots can be tested on hardware early.

    rosetta-plot prepare job.json -o out\\plot   -> out\\plot.svg + out\\plot.json
    rosetta-plot estimate out\\plot.svg
    rosetta-plot info
    rosetta-plot identify --model 5 --label "PSU Lab"
    rosetta-plot pen --model 5 --pen-down 35 --mark 10 10
    rosetta-plot trace out\\plot.svg
    rosetta-plot plot out\\plot.svg --pen-down 30 --pen-type fineliner
    rosetta-plot plot out\\plot.svg --resume

Safety rules every command follows:
  * trace, plot and pen first check the power adapter and that the job's model is the plotter's
    model, then switch the motors off so the carriage slides by hand when it is asked to be
    slid Home (EMS never releases the motors on its own);
  * anything that stops a plot (Ctrl+C, a lost cable) leaves the pen up and the progress in
    <plot>.resume.svg, and tells him how to continue.
"""
import argparse
import dataclasses
import json
import math
import sys
import threading
from pathlib import Path

from rosetta.compose import Material, PlacedPiece, Placement, compose_job, initial_placement
from rosetta.engine.identity import Identity, encode_nickname
from rosetta.engine.options import PEN_DOWN_MAX, PlotSettings
from rosetta.engine.plotter import IdentityWrite, Plotter, PlotterStopped
from rosetta.engine.runner import PlotOutcome, PlotRunner, estimate, paused_layer, set_resume_origin_home
from rosetta.errors import ImportProblem
from rosetta.loader import load_artwork
from rosetta.models import MODELS, PEN_TYPES, get_model
from rosetta.plotsvg import plot_svg

SLIDE_HOME = "Slide the pen to the corner next to the HOME label and the USB port, then press Enter. "
NO_PLOTTER = "No plotter found. Plug in the USB cable and the power adapter."
NO_PLOTTER_RETRY = ("No plotter found. Check the USB cable and power adapter, then press Enter to try again "
                    "(or type q to stop). ")
PLUG_BACK_IN = "Plug the plotter's USB cable back in, then press Enter (or type q to stop). "
PAUSED_MENU = "Paused. Type r to resume, h to send the pen Home first, or q to stop: "


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {secs:02d} s"
    return f"{secs} s"


class JobProblem(ValueError):
    """A job, plot or resume file that can't be used. The message names the file and the problem."""


# Reading job and plot files, with messages a person can act on instead of tracebacks.

_MISSING = object()


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


_KINDS = {
    "number": (_is_number, "a number"),
    "whole": (lambda value: _is_number(value) and float(value).is_integer(), "a whole number"),
    "text": (lambda value: isinstance(value, str) and value != "", "text"),
    "list": (lambda value: isinstance(value, list), "a list"),
    "object": (lambda value: isinstance(value, dict), "an object"),
    "flag": (lambda value: isinstance(value, (bool, int)) and value in (0, 1), "true or false"),
}


def _get(data: dict, key: str, where: str, kind: str, default=_MISSING):
    """data[key], checked to be of `kind`; a JobProblem naming `where` if it is missing or the wrong kind."""
    if key not in data:
        if default is _MISSING:
            raise JobProblem(f'{where}: missing "{key}"')
        return default
    value = data[key]
    check, description = _KINDS[kind]
    if not check(value):
        raise JobProblem(f'{where}: "{key}" should be {description}, not {json.dumps(value)}')
    convert = {"whole": int, "number": float, "flag": bool}.get(kind)
    return convert(value) if convert else value


def _read_text(path: Path, not_found: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8-sig")  # Notepad and PowerShell 5 may add a byte-order mark
    except FileNotFoundError:
        raise JobProblem(f"{path} not found{not_found}") from None
    except (OSError, UnicodeDecodeError) as problem:
        raise JobProblem(f"{path} couldn't be read: {problem}") from None


def _read_json(path: Path, not_found: str = "", broken: str = "") -> dict:
    text = _read_text(path, not_found)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as problem:
        raise JobProblem(f"{path} isn't valid JSON ({problem}){broken}") from None
    if not isinstance(data, dict):
        raise JobProblem(f'{path}: should be a JSON object, like {{"model": 1, ...}}{broken}')
    return data


def cmd_prepare(args) -> int:
    where = str(args.job)
    job = _read_json(args.job)
    model_number = _get(job, "model", where, "whole")
    if model_number not in MODELS:
        known = ", ".join(str(number) for number in sorted(MODELS))
        raise JobProblem(f'{where}: "model" should be one of {known}, not {model_number}')
    model = get_model(model_number)
    paper = _get(job, "material", where, "object")
    paper_where = f"{where} (material)"
    material = Material(
        _get(paper, "x", paper_where, "number", 0.0), _get(paper, "y", paper_where, "number", 0.0),
        _get(paper, "width", paper_where, "number"), _get(paper, "height", paper_where, "number"),
    )
    skip_white = _get(job, "skip_white", where, "flag", True)
    specs = _get(job, "pieces", where, "list")

    pieces = []
    for number, spec in enumerate(specs, start=1):
        piece_where = f"{where} (piece {number})"
        if not isinstance(spec, dict):
            raise JobProblem(f'{piece_where}: should be an object like {{"path": "art.svg"}}')
        path = _get(spec, "path", piece_where, "text")
        page = _get(spec, "page", piece_where, "whole", 0)
        placed = {key: _get(spec, key, piece_where, "number", None) for key in ("x", "y", "scale")}
        rotation = _get(spec, "rotation", piece_where, "whole", None)
        artwork = load_artwork((args.job.parent / path).resolve(), page)
        for issue in artwork.issues:
            print(f"  [{artwork.name}] {issue.message}")
        if rotation is not None or any(value is not None for value in placed.values()):
            placement = Placement(
                placed["x"] or 0.0, placed["y"] or 0.0,
                1.0 if placed["scale"] is None else placed["scale"], rotation or 0,
            )
        else:
            placement = initial_placement(artwork, material)
        pieces.append(PlacedPiece(artwork, placement))

    result = compose_job(model, material, pieces, skip_white=skip_white)
    if not result.groups:
        print("Nothing to plot: no lines land on the paper.")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".svg").write_text(plot_svg(model, result.groups), encoding="utf-8")
    meta = {
        "model": model.number,
        "layers": [
            {"layer": number, "color": group.color, "name": group.name}
            for number, group in enumerate(result.groups, start=1)
        ],
        "ink_bbox": list(result.ink_bbox),
        "clipped": result.clipped,
    }
    args.out.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    count = len(result.groups)
    print(f"Prepared {args.out.with_suffix('.svg')} with {count} pen color{'s' if count != 1 else ''}.")
    if result.clipped:
        print("  Some lines hang off the paper or out of reach; those parts won't be drawn.")
    return 0


def _read_plot(path: Path) -> tuple[str, dict]:
    """The plot's SVG and its checked sidecar (model, layers, ...)."""
    svg_path, json_path = path.with_suffix(".svg"), path.with_suffix(".json")
    prepare_first = " — run rosetta-plot prepare first."
    prepare_again = ". Run rosetta-plot prepare again."
    svg = _read_text(svg_path, prepare_first)
    meta = _read_json(json_path, prepare_first, prepare_again)
    where = str(json_path)
    try:
        model = _get(meta, "model", where, "whole")
        if model not in MODELS:
            raise JobProblem(f'{where}: "model" {model} is not an AxiDraw model number')
        layers = []
        for number, layer in enumerate(_get(meta, "layers", where, "list"), start=1):
            layer_where = f"{where} (layer {number})"
            if not isinstance(layer, dict):
                raise JobProblem(f"{layer_where}: should be an object")
            layers.append({
                "layer": _get(layer, "layer", layer_where, "whole"),
                "color": _get(layer, "color", layer_where, "text"),
                "name": _get(layer, "name", layer_where, "text"),
            })
        if not layers:
            raise JobProblem(f"{where}: has no layers")
    except JobProblem as problem:
        raise JobProblem(f"{problem}{prepare_again}") from None
    return svg, {**meta, "model": model, "layers": layers}


def _ink_bbox(meta: dict, where: Path) -> tuple[float, float, float, float]:
    box = meta.get("ink_bbox")
    if not (isinstance(box, list) and len(box) == 4 and all(_is_number(value) for value in box)):
        raise JobProblem(f'{where}: missing "ink_bbox". Run rosetta-plot prepare again.')
    return tuple(float(value) for value in box)


def _settings(args, meta) -> PlotSettings:
    return PlotSettings(
        model=meta["model"],
        penlift=getattr(args, "penlift", 1),
        pen_down=getattr(args, "pen_down", 30),
        pen_type=getattr(args, "pen_type", "fineliner"),
    )


def cmd_estimate(args) -> int:
    svg, meta = _read_plot(args.plot)
    settings = _settings(args, meta)
    total = 0.0
    for layer in meta["layers"]:
        result = estimate(svg, layer["layer"], settings)
        total += result.seconds
        print(f"Layer {layer['layer']} ({layer['name']}): {format_duration(result.seconds)}, "
              f"{result.pendown_m:.2f} m of drawing")
    print(f"Total: {format_duration(total)} (plus pen changes)")
    return 0


def cmd_info(args) -> int:
    plotter = Plotter()
    if not plotter.connect(PlotSettings(model=1)):
        print(NO_PLOTTER)
        return 1
    try:
        print(f"Firmware: {plotter.firmware()}")
        power = "OK" if plotter.power_ok() else "NOT DETECTED. Plug in the power adapter."
        print(f"Power adapter: {power}")
        identity = plotter.read_identity()
        if identity:
            print(f"Model: {get_model(identity.model).name} (label: {identity.label or 'none'})")
        else:
            print("Model: unknown. Run: rosetta-plot identify --model N")
    finally:
        plotter.disconnect()
    return 0


def _may_replace_name(plotter: Plotter, identity: Identity) -> bool:
    """False if the plotter already has a different name and he doesn't confirm replacing it."""
    current = plotter.nickname()
    if not current or current.strip() == encode_nickname(identity):
        return True
    print(f'This plotter is currently named "{current}".')
    return input("Replace it? Type y to continue: ").strip().lower() in ("y", "yes")


def cmd_identify(args) -> int:
    plotter = Plotter()
    if not plotter.connect(PlotSettings(model=args.model, penlift=args.penlift)):
        print(NO_PLOTTER)
        return 1
    identity = Identity(args.model, args.penlift, args.label)
    try:
        proceed = _may_replace_name(plotter, identity)
    except BaseException:
        plotter.disconnect()  # write_identity would have ended the session; nothing else will
        raise
    if not proceed:
        plotter.disconnect()
        print("Left unchanged.")
        return 1
    result = plotter.write_identity(identity)  # ends the session
    if result is IdentityWrite.WRITTEN:
        print(f"Saved: this plotter is an {get_model(args.model).name}. "
              "Wait a few seconds for it to restart before the next command.")
        return 0
    if result is IdentityWrite.FIRMWARE_TOO_OLD:
        print("This plotter's firmware is too old to store its model (needs 2.5.5 or newer).")
    elif result is IdentityWrite.FIRMWARE_UNKNOWN:
        print("Could not read this plotter's firmware version, so its model was not stored. Try again.")
    else:
        print("The plotter did not accept the model. Check the USB cable and try again.")
    return 1


# Checks before anything moves, and letting go of the carriage.

def _model_ok(identity: Identity | None, job_model: int, skip: bool, from_job: bool) -> bool:
    """Is the plotter the model the job is for? Says why not (or what it is skipping)."""
    if identity is None:
        if skip:
            print("Skipping the model check: this plotter's model isn't stored.")
            return True
        print("This plotter's model isn't stored yet. Run: rosetta-plot identify --model N")
        return False
    if identity.model == job_model:
        return True
    wanted, found = get_model(job_model).name, get_model(identity.model).name
    if skip:
        print(f"Skipping the model check: this plotter is an {found}, not an {wanted}.")
        return True
    if from_job:
        print(f'This job was prepared for an {wanted}, but this plotter is an {found}. '
              f'Prepare the job again with "model": {identity.model}.')
    else:
        print(f"You asked for an {wanted}, but this plotter is an {found}. Run it again with --model {identity.model}.")
    return False


def _preflight(args, job_model: int, from_job: bool = True) -> PlotSettings | None:
    """Make sure it is safe to move the plotter, then let go of its motors so the carriage slides.

    Needs the power adapter in and (unless --skip-model-check) a plotter whose stored model is
    the job's. Returns the settings to plot with, or None after saying what is wrong.
    """
    wanted = PlotSettings(
        model=job_model, penlift=args.penlift, pen_down=args.pen_down,
        pen_type=getattr(args, "pen_type", "fineliner"),
    )
    plotter = Plotter()
    if not plotter.connect(wanted):
        print(NO_PLOTTER)
        return None
    try:
        if not plotter.power_ok():
            print("The power adapter isn't plugged in. Plug it in and try again.")
            return None
        identity = plotter.read_identity()
        if not _model_ok(identity, job_model, getattr(args, "skip_model_check", False), from_job):
            return None
        plotter.motors_off()  # EMS leaves them holding the carriage; he is about to slide it
    except PlotterStopped as lost:
        print(f"{lost} Check the USB cable and try again.")
        return None
    finally:
        plotter.disconnect()
    return dataclasses.replace(wanted, penlift=identity.penlift if identity else args.penlift)


def _release_motors(settings: PlotSettings) -> bool:
    """Switch the motors off (pen up first) so the carriage slides by hand. False if that failed."""
    plotter = Plotter()
    try:
        if not plotter.connect(settings):
            return False
        plotter.motors_off()
        return True
    except Exception:  # a plotter that vanishes again is "not released", not a crash
        return False
    finally:
        plotter.disconnect()


def _say_it_stopped(what: str, stopped: PlotterStopped, settings: PlotSettings) -> None:
    """After a trace or pen test stopped partway: free the carriage, then tell him to slide it Home.

    Call it with the plotter's port closed; it opens the plotter once more to switch the motors off.
    """
    print(f"The plotter stopped before the {what} finished. Slide the pen Home before plotting.")
    if _release_motors(settings):
        print("  The motors are off, so the carriage slides freely.")
    else:
        print("  The motors may still be holding the carriage: unplug the power adapter before you slide it.")
    print(f"  Reason: {stopped}")


def cmd_trace(args) -> int:
    _svg, meta = _read_plot(args.plot)
    box = _ink_bbox(meta, args.plot.with_suffix(".json"))
    settings = _preflight(args, meta["model"])
    if settings is None:
        return 1
    input(SLIDE_HOME)
    plotter = Plotter()
    if not plotter.connect(settings):
        print(NO_PLOTTER)
        return 1
    stopped = None
    try:
        plotter.trace(box)
    except PlotterStopped as problem:
        stopped = problem
    finally:
        plotter.disconnect()
    if stopped is not None:
        _say_it_stopped("trace", stopped, settings)
        return 1
    print("Traced the outline and returned Home.")
    return 0


def cmd_pen(args) -> int:
    settings = _preflight(args, args.model, from_job=False)
    if settings is None:
        return 1
    input(SLIDE_HOME)
    plotter = Plotter()
    if not plotter.connect(settings):
        print(NO_PLOTTER)
        return 1
    stopped = None
    try:
        plotter.set_pen_down_height(args.pen_down)
        plotter.pen_down()
        input(f"The pen is down at {args.pen_down}%. Check it just touches the paper, "
              "then press Enter to raise it. ")
        plotter.pen_up()
        if args.mark:
            x, y = args.mark
            plotter.test_mark(x, y)
            print(f"Drew a 10 mm test line near ({x:g}, {y:g}) and returned Home.")
        else:
            print("The pen is up.")
    except PlotterStopped as problem:
        stopped = problem
    finally:
        plotter.disconnect()  # raises the pen, even after Ctrl+C
    if stopped is not None:
        _say_it_stopped("pen test", stopped, settings)
        return 1
    return 0


# Plotting.

def _run_interruptibly(work, on_interrupt):
    """Run work() on a worker thread; Ctrl+C calls on_interrupt() instead of stopping Python.

    Waits on an Event, not Thread.join(): on Python 3.12 a Ctrl+C during join(timeout) can
    mark a still-running thread as finished.
    """
    finished = threading.Event()
    outcome = {}

    def target():
        try:
            outcome["result"] = work()
        except BaseException as error:  # handed to the caller, who may be the one who can report it
            outcome["error"] = error
        finally:
            finished.set()

    threading.Thread(target=target, daemon=True).start()
    while not finished.is_set():
        try:
            finished.wait(0.2)
        except KeyboardInterrupt:
            on_interrupt()
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]


def _print_progress(progress) -> None:
    print(f"\r  {progress.pendown_mm / 1000:.2f} m drawn", end="", flush=True)


def _wants_to_stop(answer: str) -> bool:
    return answer.strip().lower()[:1] == "q"


def _paused_choice() -> str:
    """r, h or q; anything else asks again, so a typo can never put the pen back on the paper."""
    while True:
        choice = input(PAUSED_MENU).strip().lower()[:1]
        if choice in ("r", "h", "q"):
            return choice
        print("Please type r, h or q.")


def _resume_path(plot: Path) -> Path:
    return plot.with_name(plot.stem + ".resume.svg")


def _load_resume(resume_file: Path, layers: list[dict]) -> tuple[str, int]:
    """A saved paused plot and the position (in `layers`) of the layer it will finish."""
    text = _read_text(resume_file, " — there is no paused plot to resume. "
                                   "(One is saved there when you stop a plot with Ctrl+C and q.)")
    number = paused_layer(text)
    if number is None:
        raise JobProblem(f"{resume_file} doesn't hold a paused plot that can be resumed.")
    for index, layer in enumerate(layers):
        if layer["layer"] == number:
            return text, index
    raise JobProblem(f"{resume_file} is for layer {number}, which this plot doesn't have.")


def _print_estimate(svg: str, layers: list[dict], settings: PlotSettings) -> None:
    try:
        seconds = sum(estimate(svg, layer["layer"], settings).seconds for layer in layers)
    except ValueError:  # an estimate is a courtesy; the plot itself will say if the SVG is bad
        return
    print(f"About {format_duration(seconds)} of plotting, plus pen changes.")


class _PlotRun:
    """Plots the layers one pen at a time, keeping the machine safe through pauses and cable pulls.

    Progress is saved to <plot>.resume.svg whenever a run leaves resume data behind.
    """

    def __init__(self, svg: str, layers: list[dict], settings: PlotSettings, plot_path: Path):
        self.svg = svg
        self.layers = layers
        self.settings = settings
        self.plot_path = plot_path
        self.resume_file = _resume_path(plot_path)
        self.runner = PlotRunner()
        self.saved = False  # did this session save progress?

    def plot_layer(self, index: int, resume_svg: str | None = None) -> bool:
        """Draw layer `index` (or finish it from resume_svg). False if the plot was stopped for good."""
        layer = self.layers[index]
        number = layer["layer"]
        label = f"{index + 1} of {len(self.layers)} ({layer['name']})"
        action = "run" if resume_svg is None else "resume"
        while True:
            if action == "run":
                print(f"Plotting layer {label}. Press Ctrl+C to pause.")
            elif action == "resume":
                print(f"Resuming layer {label}. Press Ctrl+C to pause.")
            else:
                print("Sending the pen Home. Press Ctrl+C to pause.")
            result = self._attempt(action, number, resume_svg)
            if result.resume_svg is not None:
                resume_svg = result.resume_svg
                self._save(resume_svg)
            outcome = result.outcome

            if outcome is PlotOutcome.COMPLETED:
                if action != "home":
                    print(f"Layer {index + 1} done.")
                    return True
                print(result.message)
                input("Press Enter to resume. ")
                action = "resume"
            elif outcome is PlotOutcome.PAUSED and resume_svg is not None:
                if action == "home":
                    print(result.message)  # it stopped before the pen got Home
                choice = _paused_choice()
                if choice == "q":
                    return self.stop()
                action = "resume" if choice == "r" else "home"
            elif outcome is PlotOutcome.NOT_CONNECTED:
                # The run never started, so the pen hasn't moved: try the same thing again.
                if _wants_to_stop(input(NO_PLOTTER_RETRY)):
                    return self.stop()
            else:  # the cable was pulled, or the run failed
                self._say(result)
                if resume_svg is None:
                    return self.stop()  # nothing to come back to
                resume_svg = self._rehome(resume_svg)
                if resume_svg is None:
                    return self.stop()
                action = "resume"

    def stop(self) -> bool:
        """Free the carriage and say how things stand. Always False: the plot did not finish."""
        if _release_motors(self.settings):
            print("Stopped. The motors are off — slide the pen Home before the next plot.")
        else:
            print("Stopped. The plotter couldn't be reached, so its motors may still be on — "
                  "unplug the power adapter before you slide the pen Home.")
        if self.saved:
            print(f"Progress is saved in {self.resume_file}. "
                  f"To finish later: rosetta-plot plot {self.plot_path} --resume")
        return False

    def _attempt(self, action: str, number: int, resume_svg: str | None):
        runner, settings = self.runner, self.settings
        if action == "home":
            def work():
                return runner.return_home(resume_svg, settings)
        elif action == "resume":
            def work():
                return runner.run(resume_svg, number, settings, on_progress=_print_progress, resume=True)
        else:
            def work():
                return runner.run(self.svg, number, settings, on_progress=_print_progress)
        result = _run_interruptibly(work, self._pause)
        if action != "home":
            print()  # end the "m drawn" line
        return result

    def _pause(self) -> None:
        print("\nPausing...")
        self.runner.pause()

    def _save(self, resume_svg: str) -> None:
        try:
            self.resume_file.write_text(resume_svg, encoding="utf-8")
        except OSError as problem:
            print(f"Couldn't save progress to {self.resume_file}: {problem}")
        else:
            self.saved = True

    @staticmethod
    def _say(result) -> None:
        print(result.message)
        if result.details:
            print(f"  Details: {result.details}")

    def _rehome(self, resume_svg: str) -> str | None:
        """Wait for the cable and for him to slide the pen Home by hand; the resume data, now
        starting from Home. None if he'd rather stop."""
        while True:
            if _wants_to_stop(input(PLUG_BACK_IN)):
                return None
            if _release_motors(self.settings):
                break
            print("Still no plotter found — check the USB cable and power adapter.")
        input(SLIDE_HOME)
        return set_resume_origin_home(resume_svg)


def cmd_plot(args) -> int:
    svg, meta = _read_plot(args.plot)
    layers = meta["layers"]
    resume_file = _resume_path(args.plot)
    resume_svg, first = None, 0
    if args.resume:
        resume_svg, first = _load_resume(resume_file, layers)
    settings = _preflight(args, meta["model"])
    if settings is None:
        return 1
    if resume_svg is None:
        if resume_file.exists():
            print(f"Note: a paused plot is saved in {resume_file}, and starting over replaces it. "
                  f"To continue that one instead, press Ctrl+C now and run: rosetta-plot plot {args.plot} --resume")
        _print_estimate(svg, layers, settings)

    run = _PlotRun(svg, layers, settings, args.plot)
    try:
        input(SLIDE_HOME)
        if resume_svg is not None:
            resume_svg = set_resume_origin_home(resume_svg)  # he has just slid the pen Home
        for index in range(first, len(layers)):
            layer = layers[index]
            input(f"Load the {layer['name']} pen ({layer['color']}; {index + 1} of {len(layers)}), "
                  "then press Enter. ")
            if not run.plot_layer(index, resume_svg if index == first else None):
                return 1
    except (KeyboardInterrupt, EOFError):  # at a prompt, where Ctrl+C can't pause anything
        print()
        run.stop()
        return 130
    try:
        resume_file.unlink(missing_ok=True)
    except OSError as problem:
        print(f"Couldn't delete {resume_file} ({problem}). Delete it so it isn't resumed by mistake.")
    print("Done! The pen is back Home.")
    return 0


# Command line.

def _pen_height(text: str) -> int:
    value = int(text)
    if not 0 <= value <= PEN_DOWN_MAX:
        raise argparse.ArgumentTypeError(f"pen-down height must be 0-{PEN_DOWN_MAX}")
    return value


def _add_pen_arguments(parser, pen_type: bool = True) -> None:
    parser.add_argument("--pen-down", type=_pen_height, default=30,
                        help=f"pen-down height, percent (0-{PEN_DOWN_MAX})")
    if pen_type:
        parser.add_argument("--pen-type", choices=sorted(PEN_TYPES), default="fineliner")
    parser.add_argument("--penlift", type=int, choices=[1, 2, 3], default=1,
                        help="pen-lift type, used only if the plotter has none stored")


def _add_skip_model_check(parser) -> None:
    parser.add_argument("--skip-model-check", action="store_true",
                        help="skip the plotter-model safety check (only if you're sure)")


def _tolerate_any_text() -> None:
    """Never let a character the console can't show (like the dash in our messages) crash a plot."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):  # no stream, or not one that can be reconfigured
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="rosetta-plot", description="Rosetta Plotter (testing CLI)")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="turn a job file into a plot-ready SVG")
    prepare.add_argument("job", type=Path)
    prepare.add_argument("-o", "--out", type=Path, required=True)

    estimate_cmd = commands.add_parser("estimate", help="estimate plot time")
    estimate_cmd.add_argument("plot", type=Path)
    _add_pen_arguments(estimate_cmd)

    commands.add_parser("info", help="show the connected plotter")

    identify = commands.add_parser("identify", help="store the model on the plotter")
    identify.add_argument("--model", type=int, required=True, choices=sorted(MODELS))
    identify.add_argument("--penlift", type=int, choices=[1, 2, 3], default=1)
    identify.add_argument("--label", default="")

    pen = commands.add_parser("pen", help="check the pen-down height on paper; optionally draw a test line")
    pen.add_argument("--model", type=int, required=True, choices=sorted(MODELS))
    _add_pen_arguments(pen, pen_type=False)
    pen.add_argument("--mark", type=float, nargs=2, metavar=("X", "Y"),
                     help="after raising the pen, draw a 10 mm test line near the paper corner at X Y "
                          "(mm from Home), then return Home")
    _add_skip_model_check(pen)

    trace = commands.add_parser("trace", help="trace the drawing's outline with the pen up")
    trace.add_argument("plot", type=Path)
    _add_pen_arguments(trace)
    _add_skip_model_check(trace)

    plot = commands.add_parser("plot", help="plot, with pen-change prompts")
    plot.add_argument("plot", type=Path)
    _add_pen_arguments(plot)
    plot.add_argument("--resume", action="store_true",
                      help="finish a plot you stopped earlier (saved next to the plot as <name>.resume.svg)")
    _add_skip_model_check(plot)

    args = parser.parse_args(argv)
    handlers = {
        "prepare": cmd_prepare, "estimate": cmd_estimate, "info": cmd_info,
        "identify": cmd_identify, "pen": cmd_pen, "trace": cmd_trace, "plot": cmd_plot,
    }
    _tolerate_any_text()
    try:
        return handlers[args.command](args)
    except (ImportProblem, ValueError) as problem:  # includes JobProblem
        print(str(problem))
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\nStopped.")
        return 130
