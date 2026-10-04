"""rosetta-plot: command-line access to the Rosetta core, for testing on real plotters.

Students use the app (Plan 2). This tool exists so plots can be tested on hardware early.

    rosetta-plot prepare job.json -o out\\plot   -> out\\plot.svg + out\\plot.json
    rosetta-plot estimate out\\plot.svg
    rosetta-plot info
    rosetta-plot identify --model 5 --label "PSU Lab"
    rosetta-plot trace out\\plot.svg
    rosetta-plot plot out\\plot.svg --pen-down 30 --pen-type fineliner
"""
import argparse
import json
import threading
from pathlib import Path

from rosetta.compose import Material, PlacedPiece, Placement, compose_job, initial_placement
from rosetta.engine.identity import Identity
from rosetta.engine.options import PEN_DOWN_MAX, PlotSettings
from rosetta.engine.plotter import Plotter
from rosetta.engine.runner import PlotOutcome, PlotRunner, estimate, set_resume_origin_home
from rosetta.errors import ImportProblem
from rosetta.loader import load_artwork
from rosetta.models import MODELS, PEN_TYPES, get_model
from rosetta.plotsvg import plot_svg

HOME_INSTRUCTION = "Slide the pen to the corner next to the HOME label and the USB port."


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {secs:02d} s"
    return f"{secs} s"


def cmd_prepare(args) -> int:
    job = json.loads(args.job.read_text(encoding="utf-8"))
    model = get_model(int(job["model"]))
    paper = job["material"]
    material = Material(
        float(paper.get("x", 0)), float(paper.get("y", 0)), float(paper["width"]), float(paper["height"])
    )
    pieces = []
    for spec in job["pieces"]:
        artwork = load_artwork((args.job.parent / spec["path"]).resolve(), int(spec.get("page", 0)))
        for issue in artwork.issues:
            print(f"  [{artwork.name}] {issue.message}")
        if any(key in spec for key in ("x", "y", "scale", "rotation")):
            placement = Placement(
                float(spec.get("x", 0)), float(spec.get("y", 0)),
                float(spec.get("scale", 1.0)), int(spec.get("rotation", 0)),
            )
        else:
            placement = initial_placement(artwork, material)
        pieces.append(PlacedPiece(artwork, placement))

    result = compose_job(model, material, pieces, skip_white=bool(job.get("skip_white", True)))
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
    svg = path.with_suffix(".svg").read_text(encoding="utf-8")
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    return svg, meta


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
        print("No plotter found. Plug in the USB cable and the power adapter.")
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


def cmd_identify(args) -> int:
    plotter = Plotter()
    if not plotter.connect(PlotSettings(model=args.model)):
        print("No plotter found. Plug in the USB cable and the power adapter.")
        return 1
    if plotter.write_identity(Identity(args.model, args.penlift, args.label)):
        print(f"Saved: this plotter is an {get_model(args.model).name}. It restarts now.")
        return 0
    plotter.disconnect()
    print("This plotter's firmware is too old to store its model (needs 2.5.5 or newer).")
    return 1


def cmd_trace(args) -> int:
    _svg, meta = _read_plot(args.plot)
    input(f"{HOME_INSTRUCTION} Then press Enter. ")
    plotter = Plotter()
    if not plotter.connect(_settings(args, meta)):
        print("No plotter found. Plug in the USB cable and the power adapter.")
        return 1
    try:
        plotter.trace(tuple(meta["ink_bbox"]))
    finally:
        plotter.disconnect()
    print("Traced the outline and returned Home.")
    return 0


def _run_with_pause(runner: PlotRunner, svg: str, layer: int, settings: PlotSettings, resume=False):
    """Run in a worker thread; Ctrl+C pauses instead of killing the plot."""
    holder = {}
    worker = threading.Thread(
        target=lambda: holder.setdefault("result", runner.run(
            svg, layer, settings, on_progress=_print_progress, resume=resume)),
        daemon=True,
    )
    worker.start()
    while worker.is_alive():
        try:
            worker.join(0.2)
        except KeyboardInterrupt:
            print("\nPausing...")
            runner.pause()
    print()
    return holder["result"]


def _print_progress(progress) -> None:
    print(f"\r  {progress.pendown_mm / 1000:.2f} m drawn", end="", flush=True)


def cmd_plot(args) -> int:
    svg, meta = _read_plot(args.plot)
    settings = _settings(args, meta)
    input(f"{HOME_INSTRUCTION} Then press Enter. ")
    runner = PlotRunner()
    layers = meta["layers"]
    for index, layer in enumerate(layers, start=1):
        input(f"Load the {layer['name']} pen ({layer['color']}; {index} of {len(layers)}), "
              f"then press Enter. (Ctrl+C pauses.) ")
        result = _run_with_pause(runner, svg, layer["layer"], settings)
        while result.outcome is not PlotOutcome.COMPLETED:
            if result.outcome is PlotOutcome.PAUSED:
                choice = input("Paused. [r]esume, [h]ome then resume, [q]uit: ").strip().lower()
                if choice == "q":
                    return 1
                resume_svg = result.resume_svg
                if choice == "h":
                    home = runner.return_home(resume_svg, settings)
                    print(home.message)
                    resume_svg = home.resume_svg or resume_svg
                    input("Press Enter to resume. ")
                result = _run_with_pause(runner, resume_svg, layer["layer"], settings, resume=True)
            elif result.outcome is PlotOutcome.DISCONNECTED:
                input("Plotter disconnected. Plug the USB cable back in, then press Enter. ")
                _release_motors(settings)
                input(f"{HOME_INSTRUCTION} Then press Enter to resume. ")
                resume_svg = set_resume_origin_home(result.resume_svg)
                result = _run_with_pause(runner, resume_svg, layer["layer"], settings, resume=True)
            else:
                print(result.message)
                if result.details:
                    print(f"  Details: {result.details}")
                return 1
    print("Done! The pen is back Home.")
    return 0


def _release_motors(settings: PlotSettings) -> None:
    """After a USB loss the motors may still hold the carriage; switch them off so it slides."""
    plotter = Plotter()
    if plotter.connect(settings):
        try:
            plotter.motors_off()
        finally:
            plotter.disconnect()


def _pen_height(text: str) -> int:
    value = int(text)
    if not 0 <= value <= PEN_DOWN_MAX:
        raise argparse.ArgumentTypeError(f"pen-down height must be 0-{PEN_DOWN_MAX}")
    return value


def _add_pen_arguments(parser) -> None:
    parser.add_argument("--pen-down", type=_pen_height, default=30,
                        help=f"pen-down height, percent (0-{PEN_DOWN_MAX})")
    parser.add_argument("--pen-type", choices=sorted(PEN_TYPES), default="fineliner")
    parser.add_argument("--penlift", type=int, choices=[1, 2, 3], default=1)


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

    trace = commands.add_parser("trace", help="trace the drawing's outline with the pen up")
    trace.add_argument("plot", type=Path)
    _add_pen_arguments(trace)

    plot = commands.add_parser("plot", help="plot, with pen-change prompts")
    plot.add_argument("plot", type=Path)
    _add_pen_arguments(plot)

    args = parser.parse_args(argv)
    handlers = {
        "prepare": cmd_prepare, "estimate": cmd_estimate, "info": cmd_info,
        "identify": cmd_identify, "trace": cmd_trace, "plot": cmd_plot,
    }
    try:
        return handlers[args.command](args)
    except (ImportProblem, ValueError) as problem:
        print(str(problem))
        return 2
