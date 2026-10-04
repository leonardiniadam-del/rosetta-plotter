import json

import pytest

from rosetta.cli import format_duration, main
from rosetta.engine.plotter import IdentityWrite, PlotterStopped
from tests import samples


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


class _StubPlotter:
    """Stands in for rosetta.engine.plotter.Plotter, so the CLI's messages can be checked."""

    identity_result = None
    trace_error = None
    instances = []

    def __init__(self):
        self.disconnected = False
        _StubPlotter.instances.append(self)

    def connect(self, settings):
        return True

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
    assert "returned Home" not in text
    assert _StubPlotter.instances[0].disconnected
    _StubPlotter.trace_error = None
