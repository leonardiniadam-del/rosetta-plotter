import _thread
import argparse
import json
import threading
import time

import pytest

from rosetta import cli
from rosetta.cli import format_duration, main
from rosetta.engine.identity import Identity
from rosetta.engine.plotter import IdentityWrite, PlotterStopped
from tests import samples
from tests.cli_session import MID_STROKE, Session, make_plot, new_plotter_ebb, paused_origin
from tests.fake_ebb import FakeEBB

SLIDE = "Slide the pen to the corner next to the HOME label and the USB port, then press Enter."


def test_format_duration():
    assert format_duration(45) == "45 s"
    assert format_duration(200) == "3 min 20 s"
    assert format_duration(3720) == "1 h 02 min"


def _job(tmp_path):
    (tmp_path / "art.svg").write_bytes(samples.INKSCAPE_MM)
    job = {
        "model": 1,
        "material": {"x": 0, "y": 0, "width": 215.9, "height": 279.4},
        "pieces": [{"path": "art.svg"}],
    }
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    return job_path


def test_prepare_writes_svg_and_sidecar(tmp_path, capsys):
    out = tmp_path / "out" / "plot"
    assert main(["prepare", str(_job(tmp_path)), "-o", str(out)]) == 0
    svg = out.with_suffix(".svg").read_text(encoding="utf-8")
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert 'inkscape:label="1"' in svg
    assert meta["model"] == 1
    assert meta["layers"] == [{"layer": 1, "color": "#000000", "name": "black"}]
    assert len(meta["ink_bbox"]) == 4
    assert "1 pen color" in capsys.readouterr().out


def test_estimate_prints_per_layer_and_total(tmp_path, capsys):
    out = tmp_path / "plot"
    main(["prepare", str(_job(tmp_path)), "-o", str(out)])
    capsys.readouterr()
    assert main(["estimate", str(out.with_suffix(".svg"))]) == 0
    text = capsys.readouterr().out
    assert "Layer 1 (black)" in text
    assert "Total:" in text


def test_import_problem_is_reported_not_raised(tmp_path, capsys):
    job = {"model": 1, "material": {"width": 100, "height": 100}, "pieces": [{"path": "missing.svg"}]}
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    assert main(["prepare", str(job_path), "-o", str(tmp_path / "plot")]) == 2
    assert "can't be found" in capsys.readouterr().out


def test_unreadable_plot_is_reported_not_raised(tmp_path, capsys):
    plot = tmp_path / "broken"
    plot.with_suffix(".svg").write_text("<svg", encoding="utf-8")
    plot.with_suffix(".json").write_text(json.dumps({"model": 1, "layers": [{"layer": 1, "color": "#000000", "name": "black"}]}), encoding="utf-8")
    assert main(["estimate", str(plot.with_suffix(".svg"))]) == 2
    assert "couldn't be read" in capsys.readouterr().out


def test_pen_down_outside_the_safe_range_is_refused(tmp_path, capsys):
    import pytest

    with pytest.raises(SystemExit):
        main(["estimate", str(tmp_path / "x.svg"), "--pen-down", "95"])


# Job and plot files that can't be used: a message that names the file, not a traceback.

def _write_job(tmp_path, job):
    path = tmp_path / "job.json"
    path.write_text(job if isinstance(job, str) else json.dumps(job), encoding="utf-8")
    return path


_PAPER = {"width": 100, "height": 100}


@pytest.mark.parametrize("job, words", [
    ({"material": _PAPER, "pieces": []}, ['"model"', "missing"]),
    ({"model": 1, "pieces": []}, ['"material"', "missing"]),
    ({"model": 1, "material": _PAPER}, ['"pieces"', "missing"]),
    ({"model": 1, "material": {"height": 100}, "pieces": []}, ['"width"', "missing"]),
    ({"model": "big", "material": _PAPER, "pieces": []}, ['"model"', "number"]),
    ({"model": 1.5, "material": _PAPER, "pieces": []}, ['"model"', "whole number"]),
    ({"model": 9, "material": _PAPER, "pieces": []}, ['"model"', "9"]),
    ({"model": 1, "material": {"width": "wide", "height": 100}, "pieces": []}, ['"width"', "number"]),
    ({"model": 1, "material": _PAPER, "pieces": "art.svg"}, ['"pieces"', "list"]),
    ({"model": 1, "material": _PAPER, "pieces": [{"page": 0}]}, ['"path"', "missing"]),
    ({"model": 1, "material": _PAPER, "pieces": [{"path": "a.svg", "scale": "huge"}]}, ['"scale"', "number"]),
    ({"model": 1, "material": _PAPER, "pieces": [{"path": "a.svg", "rotation": 45.5}]}, ['"rotation"']),
    ([1, 2], ["JSON object"]),
    ("{not json", ["isn't valid JSON"]),
])
def test_prepare_names_the_file_and_the_problem_in_a_bad_job(tmp_path, capsys, job, words):
    path = _write_job(tmp_path, job)
    assert main(["prepare", str(path), "-o", str(tmp_path / "plot")]) == 2
    text = capsys.readouterr().out
    assert "job.json" in text
    for word in words:
        assert word in text
    assert "Traceback" not in text


def test_prepare_with_a_missing_job_file_says_so(tmp_path, capsys):
    assert main(["prepare", str(tmp_path / "nope.json"), "-o", str(tmp_path / "plot")]) == 2
    text = capsys.readouterr().out
    assert "nope.json" in text and "not found" in text


def test_prepare_accepts_a_job_saved_with_a_byte_order_mark(tmp_path):
    job_path = _job(tmp_path)
    job_path.write_bytes(b"\xef\xbb\xbf" + job_path.read_bytes())  # Notepad and PowerShell 5 add one
    assert main(["prepare", str(job_path), "-o", str(tmp_path / "plot")]) == 0


@pytest.mark.parametrize("command", ["estimate", "trace", "plot"])
def test_a_missing_plot_file_says_to_prepare_first(tmp_path, capsys, command):
    plot = tmp_path / "out" / "plot.svg"
    assert main([command, str(plot)]) == 2
    text = capsys.readouterr().out
    assert "plot.svg" in text and "not found" in text
    assert "rosetta-plot prepare" in text


def test_a_missing_sidecar_says_to_prepare_first(tmp_path, capsys):
    plot = make_plot(tmp_path)
    plot.with_suffix(".json").unlink()
    assert main(["plot", str(plot)]) == 2
    text = capsys.readouterr().out
    assert "plot.json" in text and "not found" in text


@pytest.mark.parametrize("sidecar, words", [
    ("{broken", ["plot.json", "isn't valid JSON"]),
    (json.dumps({"layers": []}), ['"model"', "missing"]),
    (json.dumps({"model": 1}), ['"layers"', "missing"]),
    (json.dumps({"model": 1, "layers": []}), ["no layers"]),
    (json.dumps({"model": 1, "layers": [{"layer": 1, "color": "#000000"}]}), ['"name"', "missing"]),
])
def test_a_damaged_sidecar_is_reported_with_its_file_name(tmp_path, capsys, sidecar, words):
    plot = make_plot(tmp_path)
    plot.with_suffix(".json").write_text(sidecar, encoding="utf-8")
    assert main(["plot", str(plot)]) == 2
    text = capsys.readouterr().out
    for word in words:
        assert word in text


def test_trace_without_a_bounding_box_says_to_prepare_again(tmp_path, capsys):
    plot = make_plot(tmp_path)
    meta = json.loads(plot.with_suffix(".json").read_text(encoding="utf-8"))
    del meta["ink_bbox"]
    plot.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    assert main(["trace", str(plot)]) == 2
    assert '"ink_bbox"' in capsys.readouterr().out


class _StubPlotter:
    """Stands in for rosetta.engine.plotter.Plotter, so the CLI's messages can be checked."""

    identity_result = None
    trace_error = None
    stored = Identity(1, 1, "Lab")
    instances = []

    def __init__(self):
        self.disconnected = False
        self.settings = []
        _StubPlotter.instances.append(self)

    def connect(self, settings):
        self.settings.append(settings)
        return True

    def power_ok(self):
        return True

    def nickname(self):
        return None

    def read_identity(self):
        return _StubPlotter.stored

    def motors_off(self):
        pass

    def write_identity(self, identity):
        self.disconnected = True  # the real one always ends the session
        return _StubPlotter.identity_result

    def trace(self, rect):
        if _StubPlotter.trace_error:
            raise _StubPlotter.trace_error

    def disconnect(self):
        self.disconnected = True


@pytest.mark.parametrize("result, code, words", [
    (IdentityWrite.WRITTEN, 0, "Saved"),
    (IdentityWrite.FIRMWARE_TOO_OLD, 1, "too old"),
    (IdentityWrite.FIRMWARE_UNKNOWN, 1, "Could not read"),
    (IdentityWrite.FAILED, 1, "did not accept"),
])
def test_identify_says_what_happened(monkeypatch, capsys, result, code, words):
    _StubPlotter.instances.clear()
    _StubPlotter.identity_result = result
    monkeypatch.setattr("rosetta.cli.Plotter", _StubPlotter)
    assert main(["identify", "--model", "5", "--label", "PSU Lab"]) == code
    assert words in capsys.readouterr().out
    assert _StubPlotter.instances[0].disconnected


def test_identify_connects_with_the_pen_lift_it_is_storing(monkeypatch):
    _StubPlotter.instances.clear()
    _StubPlotter.identity_result = IdentityWrite.WRITTEN
    monkeypatch.setattr("rosetta.cli.Plotter", _StubPlotter)
    assert main(["identify", "--model", "5", "--penlift", "3"]) == 0
    settings = _StubPlotter.instances[0].settings[0]
    assert (settings.model, settings.penlift) == (5, 3)


def test_identify_says_to_wait_for_the_restart(monkeypatch, capsys):
    _StubPlotter.instances.clear()
    _StubPlotter.identity_result = IdentityWrite.WRITTEN
    monkeypatch.setattr("rosetta.cli.Plotter", _StubPlotter)
    assert main(["identify", "--model", "5"]) == 0
    assert "Wait a few seconds for it to restart before the next command." in capsys.readouterr().out


def test_trace_that_is_paused_does_not_claim_to_be_home(tmp_path, monkeypatch, capsys):
    out = tmp_path / "plot"
    main(["prepare", str(_job(tmp_path)), "-o", str(out)])
    capsys.readouterr()
    _StubPlotter.instances.clear()
    _StubPlotter.trace_error = PlotterStopped("The plotter was paused or stopped before the move finished.")
    monkeypatch.setattr("rosetta.cli.Plotter", _StubPlotter)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert main(["trace", str(out.with_suffix(".svg"))]) == 1
    text = capsys.readouterr().out
    assert "paused or stopped" in text
    assert "stopped before the trace finished. Slide the pen Home before plotting." in text
    assert "returned Home" not in text
    # the pre-flight check, the trace, and letting go of the motors afterwards each opened (and closed) the plotter
    assert len(_StubPlotter.instances) == 3
    assert all(plotter.disconnected for plotter in _StubPlotter.instances)
    _StubPlotter.trace_error = None


def test_preflight_plots_with_the_stored_pen_lift_and_the_jobs_model(monkeypatch):
    _StubPlotter.instances.clear()
    _StubPlotter.stored = Identity(1, 3, "Lab")
    monkeypatch.setattr("rosetta.cli.Plotter", _StubPlotter)
    args = argparse.Namespace(penlift=1, pen_down=42, pen_type="marker", skip_model_check=False)
    try:
        settings = cli._preflight(args, 1)
    finally:
        _StubPlotter.stored = Identity(1, 1, "Lab")
    assert (settings.model, settings.penlift, settings.pen_down, settings.pen_type) == (1, 3, 42, "marker")
    assert _StubPlotter.instances[0].disconnected


def test_preflight_without_a_stored_identity_uses_the_penlift_asked_for(monkeypatch):
    _StubPlotter.instances.clear()
    _StubPlotter.stored = None
    monkeypatch.setattr("rosetta.cli.Plotter", _StubPlotter)
    args = argparse.Namespace(penlift=2, pen_down=30, pen_type="fineliner", skip_model_check=True)
    try:
        settings = cli._preflight(args, 1)
    finally:
        _StubPlotter.stored = Identity(1, 1, "Lab")
    assert settings.penlift == 2


# Waiting on the worker thread.

def test_ctrl_c_while_waiting_does_not_abandon_the_worker():
    """On Python 3.12 a Ctrl+C inside Thread.join(timeout) can mark a running thread as finished."""
    done = []

    def work():
        time.sleep(0.5)
        done.append(True)
        return "finished"

    interrupts = []
    threading.Timer(0.15, _thread.interrupt_main).start()
    assert cli._run_interruptibly(work, lambda: interrupts.append(True)) == "finished"
    assert interrupts == [True]
    assert done == [True]  # it waited for the work to really end


def test_run_interruptibly_reraises_what_the_work_raised():
    def work():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        cli._run_interruptibly(work, lambda: None)


# Whole sessions at the keyboard, with a real EMS engine and a fake plotter.

def _watch_slide_prompts(session):
    """At every "slide the pen" prompt, note whether the last motor command was 'motors off'."""
    released = []

    def check(s):
        commands = [command for command in s.plotter.log if command.startswith("EM,")]
        released.append(bool(commands) and commands[-1] == "EM,0,0")

    session.when_prompted("Slide the pen to the corner", check, once=False)
    return released


def _resume_file(tmp_path):
    return tmp_path / "plot.resume.svg"


def test_a_normal_two_layer_plot_draws_both_layers_and_leaves_nothing_behind(tmp_path):
    plot = make_plot(tmp_path)
    session = Session(["", "", ""])
    released = _watch_slide_prompts(session)
    assert session.run(["plot", plot]) == 0, session.output
    assert session.answers == []
    assert released == [True]  # the motors were off when he was asked to slide the carriage
    assert session.runs == 2
    assert all(session.drew(ebb) for ebb in session.engine_ebbs)
    assert all(ebb.pen_cmds[-1][0] == "up" for ebb in session.engine_ebbs)
    assert all(ebb.closed for ebb in session.engine_ebbs)
    assert session.plotter.closed
    assert not _resume_file(tmp_path).exists()
    assert session.prompts[0] == SLIDE + " "
    assert session.prompts[1] == "Load the black pen (#000000; 1 of 2), then press Enter. "
    assert session.prompts[2] == "Load the red pen (#ff0000; 2 of 2), then press Enter. "
    assert "About " in session.output and "of plotting, plus pen changes." in session.output
    assert "Plotting layer 1 of 2 (black). Press Ctrl+C to pause." in session.output
    assert "Layer 1 done." in session.output
    assert "Plotting layer 2 of 2 (red). Press Ctrl+C to pause." in session.output
    assert "Ctrl+C pauses" not in "".join(session.prompts)  # Ctrl+C does nothing at a prompt
    assert "Done! The pen is back Home." in session.output


def _pause_in_layer_one(tmp_path, answers):
    """A two-layer plot with Ctrl+C pressed in the middle of the first stroke of layer 1."""
    plot = make_plot(tmp_path)
    first = FakeEBB()
    session = Session(answers, runner_ebbs=[first])
    session.press_ctrl_c_at(first, MID_STROKE)
    return plot, first, session


def test_a_plot_whose_time_cannot_be_estimated_still_plots(tmp_path, monkeypatch):
    def cannot(*args, **kwargs):
        raise ValueError("This plot couldn't be read.")

    monkeypatch.setattr(cli, "estimate", cannot)
    plot = make_plot(tmp_path)
    session = Session(["", "", ""])
    assert session.run(["plot", plot]) == 0, session.output
    assert "About " not in session.output
    assert session.runs == 2


@pytest.mark.parametrize("choice", ["r", "R", "resume"])
def test_ctrl_c_pauses_and_r_resumes_the_layer(tmp_path, choice):
    plot, first, session = _pause_in_layer_one(tmp_path, ["", "", choice, ""])
    released = _watch_slide_prompts(session)
    assert session.run(["plot", plot]) == 0, session.output
    assert session.answers == []
    assert released == [True]
    assert session.runs == 3  # the paused run, the resume, layer 2
    assert "Pausing..." in session.output
    assert first.pen_cmds[-1][0] == "up"  # the pause lifted the pen
    assert session.drew(first) and session.drew(session.engine_ebbs[1]) and session.drew(session.engine_ebbs[2])
    assert all(ebb.closed for ebb in session.engine_ebbs)
    assert session.times_asked("Paused.") == 1
    assert "Resuming layer 1 of 2 (black). Press Ctrl+C to pause." in session.output
    assert not _resume_file(tmp_path).exists()  # the whole plot completed
    # Resuming right after a pause: nobody moved the carriage, so it carries on from where it stopped.
    assert [(call.kind, call.layer) for call in session.calls] == [("run", 1), ("resume", 1), ("run", 2)]
    assert session.calls[1].origin != (0.0, 0.0)


def test_ctrl_c_pauses_and_h_sends_the_pen_home_before_resuming(tmp_path):
    plot, first, session = _pause_in_layer_one(tmp_path, ["", "", "h", "", ""])
    released = _watch_slide_prompts(session)
    assert session.run(["plot", plot]) == 0, session.output
    assert session.answers == []
    assert released == [True]
    assert session.runs == 4  # the paused run, the trip Home, the resume, layer 2
    home, resume, layer_two = session.engine_ebbs[1:]
    assert home.sm > 0 and not session.drew(home)  # the trip Home moves but draws nothing
    assert session.drew(resume) and session.drew(layer_two)
    assert "The pen is back at Home." in session.output
    assert session.times_asked("Press Enter to resume. ") == 1
    assert [(call.kind, call.layer) for call in session.calls] == [
        ("run", 1), ("home", None), ("resume", 1), ("run", 2)]
    assert session.calls[2].origin == pytest.approx((0.0, 0.0), abs=0.1)  # the resume starts at Home
    assert all(ebb.closed for ebb in session.engine_ebbs)
    assert not _resume_file(tmp_path).exists()


def test_the_paused_menu_ignores_anything_but_r_h_or_q(tmp_path):
    plot = make_plot(tmp_path)
    first = FakeEBB()
    session = Session(["", "", "x", "", "stop", "resume now", ""], runner_ebbs=[first])
    session.press_ctrl_c_at(first, MID_STROKE)
    assert session.run(["plot", plot]) == 0, session.output
    assert session.answers == []
    assert session.times_asked("Paused.") == 4  # "x", Enter and "stop" each asked again
    assert session.runs == 3  # nothing resumed until the "r"


def test_the_paused_menu_prompt_text(tmp_path):
    plot = make_plot(tmp_path)
    first = FakeEBB()
    session = Session(["", "", "q"], runner_ebbs=[first])
    session.press_ctrl_c_at(first, MID_STROKE)
    session.run(["plot", plot])
    assert "Paused. Type r to resume, h to send the pen Home first, or q to stop: " in session.prompts


def test_quitting_a_paused_plot_frees_the_carriage_and_saves_progress_then_resume_finishes_it(tmp_path):
    plot = make_plot(tmp_path)
    first = FakeEBB()
    session = Session(["", "", "q"], runner_ebbs=[first])
    session.press_ctrl_c_at(first, MID_STROKE)
    session.when_prompted("Paused.", lambda s: s.plotter.log.clear())  # only what happens from here
    assert session.run(["plot", plot]) == 1, session.output
    assert "EM,0,0" in session.plotter.log
    assert session.plotter.closed
    assert _resume_file(tmp_path).exists()
    assert ("Stopped. The motors are off — slide the pen Home before the next plot.\n"
            f"Progress is saved in {_resume_file(tmp_path)}. "
            f"To finish later: rosetta-plot plot {plot} --resume") in session.output

    saved_text = _resume_file(tmp_path).read_text(encoding="utf-8")
    later = Session(["", "", ""], runner_ebbs=[FakeEBB(), FakeEBB()])
    released = _watch_slide_prompts(later)
    assert later.run(["plot", plot, "--resume"]) == 0, later.output
    assert later.answers == []
    assert released == [True]
    assert later.prompts[0] == SLIDE + " "
    assert "Load the black pen (#000000; 1 of 2)" in later.prompts[1]  # the paused layer first...
    assert "Load the red pen (#ff0000; 2 of 2)" in later.prompts[2]  # ...then the rest
    assert later.runs == 2
    assert all(later.drew(ebb) for ebb in later.engine_ebbs)
    assert not _resume_file(tmp_path).exists()
    assert "Resuming layer 1 of 2 (black)." in later.output
    assert "About " not in later.output  # no estimate for a half-done layer
    # The saved file says where the pen stopped; he has slid it Home since, so the resume starts from Home.
    assert [(call.kind, call.layer) for call in later.calls] == [("resume", 1), ("run", 2)]
    assert paused_origin(saved_text) != (0.0, 0.0)
    assert later.calls[0].origin == (0.0, 0.0)


def test_resume_without_a_saved_plot_says_so(tmp_path):
    plot = make_plot(tmp_path)
    session = Session([])
    assert session.run(["plot", plot, "--resume"]) == 2
    assert "plot.resume.svg" in session.output and "not found" in session.output
    assert session.prompts == [] and session.runs == 0


def test_resume_of_a_layer_the_plot_does_not_have_is_refused(tmp_path):
    plot = make_plot(tmp_path)
    first = FakeEBB()
    session = Session(["", "", "q"], runner_ebbs=[first])
    session.press_ctrl_c_at(first, MID_STROKE)
    session.run(["plot", plot])
    saved = _resume_file(tmp_path)
    saved.write_text(saved.read_text(encoding="utf-8").replace('layer="1"', 'layer="7"'), encoding="utf-8")
    later = Session([])
    assert later.run(["plot", plot, "--resume"]) == 2
    assert "layer" in later.output and "plot.resume.svg" in later.output
    assert later.runs == 0


def test_ctrl_c_at_the_paused_menu_stops_with_the_carriage_free_and_progress_saved(tmp_path):
    plot = make_plot(tmp_path)
    first = FakeEBB()
    session = Session(["", "", KeyboardInterrupt()], runner_ebbs=[first])
    session.press_ctrl_c_at(first, MID_STROKE)
    session.when_prompted("Paused.", lambda s: s.plotter.log.clear())
    assert session.run(["plot", plot]) == 130, session.output
    assert "EM,0,0" in session.plotter.log
    assert _resume_file(tmp_path).exists()
    assert "--resume" in session.output and "motors are off" in session.output
    assert "Traceback" not in session.output


def test_a_lost_usb_cable_is_recovered_after_a_failed_replug(tmp_path):
    plot = make_plot(tmp_path)
    dies = FakeEBB(die_after_moves=20)
    session = Session(["", "", "", "", "", ""], runner_ebbs=[dies])
    session.when_prompted("Plug the plotter's USB cable", lambda s: setattr(s, "connect_failures", 1))
    saved = []
    session.when_prompted("Plug the plotter's USB cable",
                          lambda s: saved.append(_resume_file(tmp_path).read_text(encoding="utf-8")))
    released = _watch_slide_prompts(session)
    assert session.run(["plot", plot]) == 0, session.output
    assert session.answers == []
    # The progress was saved when the cable was lost; after he slid the pen Home it resumes from Home.
    assert paused_origin(saved[0]) != (0.0, 0.0)
    assert [(call.kind, call.layer) for call in session.calls] == [("run", 1), ("resume", 1), ("run", 2)]
    assert session.calls[1].origin == (0.0, 0.0)
    assert "Plotter disconnected." in session.output
    assert session.times_asked("Plug the plotter's USB cable back in, then press Enter (or type q to stop). ") == 2
    assert "Still no plotter found — check the USB cable and power adapter." in session.output
    assert released == [True, True]  # the start, then again after the replug
    assert session.times_asked("Slide the pen to the corner") == 2
    assert session.runs == 3  # the plot that died, the resume, layer 2
    assert session.drew(session.engine_ebbs[1]) and session.drew(session.engine_ebbs[2])
    assert all(ebb.closed for ebb in session.engine_ebbs)
    assert not _resume_file(tmp_path).exists()


def test_quitting_after_a_lost_usb_cable_keeps_the_progress(tmp_path):
    plot = make_plot(tmp_path)
    session = Session(["", "", "q"], runner_ebbs=[FakeEBB(die_after_moves=20)])
    assert session.run(["plot", plot]) == 1, session.output
    assert _resume_file(tmp_path).exists()
    assert "--resume" in session.output
    assert "The motors are off" in session.output  # the plotter was reachable again, so they are off


def test_a_stop_with_no_plotter_to_release_says_to_unplug_the_power(tmp_path):
    plot = make_plot(tmp_path)
    session = Session(["", "", "q"], runner_ebbs=[FakeEBB(die_after_moves=20)])
    session.when_prompted("Plug the plotter's USB cable", lambda s: setattr(s, "no_plotter", True))
    assert session.run(["plot", plot]) == 1, session.output
    assert _resume_file(tmp_path).exists()
    assert "motors are off" not in session.output  # it couldn't switch them off, and doesn't claim to
    assert "unplug the power adapter" in session.output.split("Stopped.")[1]
    assert "--resume" in session.output


def test_no_plotter_on_a_fresh_layer_offers_to_try_again(tmp_path):
    plot = make_plot(tmp_path)
    session = Session(["", "", "", ""], runner_ebbs=[None])
    assert session.run(["plot", plot]) == 0, session.output
    assert session.answers == []
    prompt = "No plotter found. Check the USB cable and power adapter, then press Enter to try again (or type q to stop). "
    assert session.times_asked(prompt) == 1
    assert session.runs == 3  # the try that found nothing, the retry, layer 2
    assert session.engine_ebbs[0] is None
    assert session.drew(session.engine_ebbs[1]) and session.drew(session.engine_ebbs[2])
    assert session.times_asked("Load the black pen") == 1  # the retry doesn't ask for the pen again


def test_giving_up_when_no_plotter_is_found_saves_nothing_to_resume(tmp_path):
    plot = make_plot(tmp_path)
    session = Session(["", "", "q"], runner_ebbs=[None])
    assert session.run(["plot", plot]) == 1, session.output
    assert not _resume_file(tmp_path).exists()
    assert "--resume" not in session.output
    assert "Stopped." in session.output


def test_no_plotter_while_going_home_after_a_pause_is_retried(tmp_path):
    plot = make_plot(tmp_path)
    first = FakeEBB()
    session = Session(["", "", "h", "", "", ""], runner_ebbs=[first, None])
    session.press_ctrl_c_at(first, MID_STROKE)
    assert session.run(["plot", plot]) == 0, session.output
    assert session.answers == []
    assert session.runs == 5  # layer 1 (paused), Home (nothing found), Home, the rest of layer 1, layer 2
    assert session.engine_ebbs[1] is None
    assert not session.drew(session.engine_ebbs[2]) and session.engine_ebbs[2].sm > 0
    assert session.drew(session.engine_ebbs[3]) and session.drew(session.engine_ebbs[4])


def test_a_lost_cable_on_the_way_home_rehomes_by_hand_and_resumes(tmp_path):
    plot = make_plot(tmp_path)
    first = FakeEBB()
    session = Session(["", "", "h", "", "", ""], runner_ebbs=[first, FakeEBB(die_after_moves=3)])
    session.press_ctrl_c_at(first, MID_STROKE)
    released = _watch_slide_prompts(session)
    assert session.run(["plot", plot]) == 0, session.output
    assert session.answers == []
    assert released == [True, True]
    assert session.times_asked("Plug the plotter's USB cable") == 1
    assert session.runs == 4  # layer 1 (paused), Home (cable lost), the rest of layer 1, layer 2
    assert not _resume_file(tmp_path).exists()


def test_a_failed_resume_asks_to_rehome_and_tries_again(tmp_path):
    plot = make_plot(tmp_path)
    first = FakeEBB()
    session = Session(["", "", "r", "", "", ""], runner_ebbs=[first, RuntimeError("serial exploded")])
    session.press_ctrl_c_at(first, MID_STROKE)
    released = _watch_slide_prompts(session)
    assert session.run(["plot", plot]) == 0, session.output
    assert session.answers == []
    assert "The plot stopped unexpectedly." in session.output
    assert "  Details: RuntimeError: serial exploded" in session.output
    assert released == [True, True]
    assert session.runs == 4
    assert not _resume_file(tmp_path).exists()


def test_a_failed_first_run_has_nothing_to_resume_so_it_stops_with_the_carriage_free(tmp_path):
    plot = make_plot(tmp_path)
    session = Session(["", ""], runner_ebbs=[RuntimeError("serial exploded")])
    session.when_prompted("Load the black pen", lambda s: s.plotter.log.clear())
    assert session.run(["plot", plot]) == 1, session.output
    assert "The plot stopped unexpectedly." in session.output
    assert "  Details: RuntimeError: serial exploded" in session.output
    assert "EM,0,0" in session.plotter.log
    assert "The motors are off" in session.output
    assert not _resume_file(tmp_path).exists()
    assert session.runs == 1


def test_ctrl_c_between_layers_stops_cleanly_with_the_motors_off(tmp_path):
    plot = make_plot(tmp_path)
    session = Session(["", "", KeyboardInterrupt()])
    session.when_prompted("Load the red pen", lambda s: s.plotter.log.clear())
    assert session.run(["plot", plot]) == 130, session.output
    assert "EM,0,0" in session.plotter.log
    assert "Stopped." in session.output
    assert "Traceback" not in session.output


def test_a_saved_pause_is_mentioned_when_starting_over(tmp_path):
    plot = make_plot(tmp_path)
    _resume_file(tmp_path).write_text("old", encoding="utf-8")
    session = Session(["", "", ""])
    assert session.run(["plot", plot]) == 0, session.output
    assert "plot.resume.svg" in session.output and "--resume" in session.output.split("Slide the pen")[0]
    assert not _resume_file(tmp_path).exists()  # a finished plot clears it


# The pre-flight check: nothing moves unless the plotter is plugged in and is the right model.

@pytest.mark.parametrize("command", ["plot", "trace"])
@pytest.mark.parametrize("plotter_args, message", [
    (dict(nickname=""),
     "This plotter's model isn't stored yet. Run: rosetta-plot identify --model N"),
    (dict(nickname="Lab m5p1"),
     'This job was prepared for an AxiDraw V2 / V3 / SE/A4, but this plotter is an AxiDraw SE/A1. '
     'Prepare the job again with "model": 5.'),
    (dict(nickname="Lab m1p1", voltage=0),
     "The power adapter isn't plugged in. Plug it in and try again."),
])
def test_preflight_refuses_an_unsafe_plotter_before_anything_moves(tmp_path, command, plotter_args, message):
    plot = make_plot(tmp_path)
    ebb = new_plotter_ebb(**plotter_args)
    session = Session([], plotter=ebb)  # no answers: nothing may be asked
    assert session.run([command, plot]) == 1, session.output
    assert message in session.output
    assert session.prompts == []
    assert session.runs == 0
    assert ebb.sm == 0 and "down" not in session.pen_commands(ebb)
    assert ebb.closed


def test_preflight_with_no_plotter_connected_says_so(tmp_path):
    plot = make_plot(tmp_path)
    session = Session([], no_plotter=True)
    assert session.run(["plot", plot]) == 1
    assert "No plotter found. Plug in the USB cable and the power adapter." in session.output
    assert session.prompts == []


def test_skip_model_check_lets_a_plotter_with_no_stored_model_plot(tmp_path):
    plot = make_plot(tmp_path)
    session = Session(["", "", ""], plotter=new_plotter_ebb(nickname=""))
    assert session.run(["plot", plot, "--skip-model-check"]) == 0, session.output
    assert session.runs == 2
    assert "isn't stored" in session.output  # it says what it skipped


def test_skip_model_check_lets_a_mismatched_plotter_plot_but_says_so(tmp_path):
    plot = make_plot(tmp_path)
    session = Session(["", "", ""], plotter=new_plotter_ebb(nickname="Lab m5p1"))
    assert session.run(["plot", plot, "--skip-model-check"]) == 0, session.output
    assert "AxiDraw SE/A1" in session.output


def test_skip_model_check_does_not_skip_the_power_check(tmp_path):
    plot = make_plot(tmp_path)
    session = Session([], plotter=new_plotter_ebb(voltage=0))
    assert session.run(["plot", plot, "--skip-model-check"]) == 1
    assert "power adapter" in session.output and session.runs == 0


def test_a_job_for_the_right_model_passes_the_preflight_and_motors_come_off(tmp_path):
    plot = make_plot(tmp_path, model=5)
    ebb = new_plotter_ebb(nickname="PSU Lab m5p1")
    session = Session(["", "", ""], plotter=ebb)
    released = _watch_slide_prompts(session)
    assert session.run(["plot", plot]) == 0, session.output
    assert released == [True]


# trace

def test_trace_goes_around_the_drawing_and_home_with_the_motors_off_for_the_slide(tmp_path):
    plot = make_plot(tmp_path)
    session = Session([""])
    released = _watch_slide_prompts(session)
    assert session.run(["trace", plot]) == 0, session.output
    assert released == [True]
    ebb = session.plotter
    assert ebb.sm > 0 and "down" not in session.pen_commands(ebb)
    assert abs(ebb.sm_steps1) <= 2 and abs(ebb.sm_steps2) <= 2  # back Home
    assert ebb.closed
    assert "Traced the outline and returned Home." in session.output


def test_trace_stopped_by_the_pause_button_frees_the_carriage_before_asking_him_to_slide_it(tmp_path):
    plot = make_plot(tmp_path)
    session = Session([""], plotter=new_plotter_ebb(button_after_moves=40))
    assert session.run(["trace", plot]) == 1, session.output
    assert "The plotter stopped before the trace finished. Slide the pen Home before plotting." in session.output
    assert "returned Home" not in session.output
    assert "The motors are off, so the carriage slides freely." in session.output
    assert session.plotter.log.count("EM,0,0") == 2  # once before the trace, once after it stopped
    assert [c for c in session.plotter.log if c.startswith("EM,")][-1] == "EM,0,0"
    assert session.plotter.closed


def test_trace_that_lost_the_cable_says_to_unplug_the_power_before_sliding(tmp_path):
    plot = make_plot(tmp_path)
    session = Session([""], plotter=new_plotter_ebb(die_after_moves=40))
    assert session.run(["trace", plot]) == 1, session.output
    assert "Slide the pen Home before plotting." in session.output
    assert "unplug the power adapter before you slide it" in session.output
    assert "  Reason: " in session.output
    assert "The motors are off" not in session.output  # it could not switch them off, and doesn't say so


# pen

def test_pen_lowers_the_pen_waits_then_draws_a_test_mark_and_goes_home(tmp_path):
    session = Session(["", ""])
    ebb = session.plotter
    at_the_check = []
    session.when_prompted("Check it just touches", lambda s: at_the_check.append(s.pen_commands(ebb)[-1]))
    released = _watch_slide_prompts(session)
    assert session.run(["pen", "--model", "1", "--pen-down", "35", "--mark", "10", "10"]) == 0, session.output
    assert released == [True]
    assert session.prompts[1] == "The pen is down at 35%. Check it just touches the paper, then press Enter to raise it. "
    assert at_the_check == ["down"]  # the pen really was down while he looked
    assert "Drew a 10 mm test line near (10, 10) and returned Home." in session.output
    assert any(command == "down" and moves > 0 for command, moves in ebb.pen_cmds)  # the line itself
    assert ebb.pen_cmds[-1][0] == "up"
    assert abs(ebb.sm_steps1) <= 2 and abs(ebb.sm_steps2) <= 2  # ends Home
    assert ebb.closed


def test_pen_without_a_mark_only_checks_the_height(tmp_path):
    session = Session(["", ""])
    assert session.run(["pen", "--model", "1"]) == 0, session.output
    ebb = session.plotter
    commands = session.pen_commands(ebb)
    assert "down" in commands and commands[-1] == "up"
    assert ebb.sm == 0
    assert "test line" not in session.output
    assert ebb.closed


def test_a_pen_test_stopped_by_the_pause_button_frees_the_carriage_and_says_so(tmp_path):
    session = Session(["", ""], plotter=new_plotter_ebb(button_after_moves=5))
    assert session.run(["pen", "--model", "1", "--mark", "10", "10"]) == 1, session.output
    assert "The plotter stopped before the pen test finished. Slide the pen Home before plotting." in session.output
    assert "returned Home" not in session.output
    assert "The motors are off, so the carriage slides freely." in session.output
    assert session.plotter.log.count("EM,0,0") == 2
    assert session.plotter.pen_cmds[-1][0] == "up"
    assert session.plotter.closed


def test_ctrl_c_while_the_pen_is_down_lifts_it(tmp_path):
    session = Session(["", KeyboardInterrupt()])
    assert session.run(["pen", "--model", "1"]) == 130, session.output
    ebb = session.plotter
    assert ebb.pen_cmds[-1][0] == "up"
    assert ebb.closed


def test_pen_refuses_a_plotter_of_another_model(tmp_path):
    session = Session([], plotter=new_plotter_ebb(nickname="Lab m5p1"))
    assert session.run(["pen", "--model", "1"]) == 1
    assert "--model 5" in session.output
    assert session.prompts == []


def test_pen_refuses_an_unpowered_plotter(tmp_path):
    session = Session([], plotter=new_plotter_ebb(voltage=0))
    assert session.run(["pen", "--model", "1"]) == 1
    assert "power adapter" in session.output


def test_pen_down_height_over_the_safe_range_is_refused():
    with pytest.raises(SystemExit):
        main(["pen", "--model", "1", "--pen-down", "95"])


# identify

def test_identify_declined_leaves_a_foreign_name_alone(tmp_path):
    ebb = new_plotter_ebb(nickname="Studio Plotter")
    session = Session(["n"], plotter=ebb)
    assert session.run(["identify", "--model", "5", "--label", "PSU Lab"]) == 1, session.output
    assert 'This plotter is currently named "Studio Plotter".' in session.output
    assert session.prompts == ["Replace it? Type y to continue: "]
    assert "Left unchanged." in session.output
    assert ebb.nickname == "Studio Plotter"
    assert not any(command.startswith(("ST,", "RB")) for command in ebb.log)
    assert ebb.closed


@pytest.mark.parametrize("answer", ["", "maybe", "no"])
def test_identify_replaces_nothing_unless_told_y(answer):
    ebb = new_plotter_ebb(nickname="Studio Plotter")
    session = Session([answer], plotter=ebb)
    assert session.run(["identify", "--model", "5"]) == 1
    assert ebb.nickname == "Studio Plotter"


def test_identify_replaces_a_foreign_name_when_told_y():
    ebb = new_plotter_ebb(nickname="Studio Plotter")
    session = Session(["y"], plotter=ebb)
    assert session.run(["identify", "--model", "5", "--label", "PSU Lab"]) == 0, session.output
    assert ebb.nickname == "PSU Lab m5p1"
    assert "Saved: this plotter is an AxiDraw SE/A1." in session.output
    assert "Wait a few seconds for it to restart before the next command." in session.output
    assert ebb.closed


def test_identify_does_not_ask_when_the_name_is_already_right_or_blank():
    for nickname in ("PSU Lab m5p1", ""):
        session = Session([], plotter=new_plotter_ebb(nickname=nickname))  # no answers: no questions
        assert session.run(["identify", "--model", "5", "--label", "PSU Lab"]) == 0, session.output


def test_identify_with_no_plotter_connected_says_so():
    session = Session([], no_plotter=True)
    assert session.run(["identify", "--model", "5"]) == 1
    assert "No plotter found." in session.output


# Ctrl+C and end-of-input at a prompt

@pytest.mark.parametrize("error", [KeyboardInterrupt(), EOFError()])
def test_ctrl_c_or_end_of_input_at_a_prompt_stops_without_a_traceback(tmp_path, error):
    plot = make_plot(tmp_path)
    session = Session([error])
    assert session.run(["trace", plot]) == 130
    assert "\nStopped." in session.output
    assert "Traceback" not in session.output
    assert session.plotter.closed


def test_ctrl_c_at_the_first_prompt_of_a_plot_stops_without_a_traceback(tmp_path):
    plot = make_plot(tmp_path)
    session = Session([KeyboardInterrupt()])
    assert session.run(["plot", plot]) == 130
    assert "Stopped." in session.output
    assert session.runs == 0
