"""The --smoke-check mode (rosetta.app.smoke): argument parsing, the no-hardware guarantee, and the
result file. The real window is replaced by a stand-in here; the build script runs the real thing."""
import json

import pytest
import serial
from plotink import ebb_serial

import rosetta
from rosetta.app import main, smoke


@pytest.mark.parametrize("argv, expected", [
    ([], None),
    (["--other"], None),
    (["--smoke-check", "out.json"], "out.json"),
    (["--smoke-check=out.json"], "out.json"),
    (["-x", "--smoke-check", "C:\\some folder\\r.json"], "C:\\some folder\\r.json"),
])
def test_result_path(argv, expected):
    found = smoke.result_path(argv)
    assert (None if found is None else str(found)) == expected


@pytest.mark.parametrize("argv", [["--smoke-check"], ["--smoke-check="], ["--smoke-check", "--other"]])
def test_the_flag_needs_a_file(argv):
    with pytest.raises(smoke.UsageError):
        smoke.result_path(argv)


def _no_window(*args, **kwargs):
    raise AssertionError("no window may open")


def test_a_bad_flag_opens_nothing(monkeypatch):
    monkeypatch.setattr(main, "start_gui", _no_window)
    monkeypatch.setattr(main, "open_window", _no_window)
    assert main.main(["--smoke-check"]) == 2


def test_the_flag_runs_the_check_instead_of_the_app(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(smoke, "run", lambda path: seen.append(path) or 0)
    monkeypatch.setattr(main, "setup_logging", _no_window)  # the app's own start-up is skipped
    monkeypatch.setattr(main, "start_gui", _no_window)
    assert main.main(["--smoke-check", str(tmp_path / "r.json")]) == 0
    assert seen == [tmp_path / "r.json"]


def test_the_check_uses_the_stand_in_plotter(tmp_path):
    api, sink = smoke.make_api(tmp_path)
    try:
        assert api._machine._new_plotter is smoke.NoPlotter
        assert smoke.NoPlotter().connect(None) is False
    finally:
        sink.close()


def test_no_serial_port_can_be_found_or_opened(monkeypatch):
    # Let monkeypatch put the real (already test-guarded) functions back afterwards.
    for name in smoke.PORT_SEARCHES:
        monkeypatch.setattr(ebb_serial, name, getattr(ebb_serial, name))
    monkeypatch.setattr(ebb_serial, "comports", ebb_serial.comports)
    monkeypatch.setattr(serial, "Serial", serial.Serial)

    smoke.no_serial_ports()

    for name in smoke.PORT_SEARCHES:
        assert getattr(ebb_serial, name)() is None
    assert ebb_serial.comports() == []
    with pytest.raises(serial.SerialException):
        serial.Serial("COM3")


class _FakeWindow:
    def __init__(self, answers):
        self._answers = answers
        self.destroyed = False

    def evaluate_js(self, script):
        return self._answers(script)

    def destroy(self):
        self.destroyed = True


@pytest.fixture
def fake_gui(monkeypatch, tmp_path):
    """run() with a stand-in window: answers(script) decides what the page says."""
    windows = []
    monkeypatch.setattr(smoke, "no_serial_ports", lambda: None)  # the conftest guard is already in place
    monkeypatch.setattr(main, "ui_entry", lambda: str(tmp_path / "index.html"))

    def use(answers):
        def open_window(api, sink, entry):
            windows.append(_FakeWindow(answers))
            return windows[-1]

        monkeypatch.setattr(main, "open_window", open_window)
        monkeypatch.setattr(main, "start_gui", lambda func=None: func())
        return windows

    return use


def test_a_ready_page_passes(fake_gui, tmp_path):
    windows = fake_gui(lambda script: True)
    out = tmp_path / "result" / "r.json"
    assert smoke.run(out) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["ready"] is True and result["shell"] is True
    assert result["version"] == rosetta.__version__
    assert result["error"] is None and result["missing"] == []
    assert windows[0].destroyed


def test_a_page_that_never_renders_fails_in_time(fake_gui, tmp_path):
    windows = fake_gui(lambda script: script != smoke.SHELL_RENDERED)  # ready, but no shell
    out = tmp_path / "r.json"
    assert smoke.run(out, timeout_s=0.5) == 1
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["ready"] is True and result["shell"] is False
    assert "wasn't ready" in result["error"]
    assert windows[0].destroyed


def test_a_missing_page_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(smoke, "no_serial_ports", lambda: None)
    monkeypatch.setattr(main, "ui_entry", lambda: None)
    monkeypatch.setattr(main, "open_window", _no_window)
    out = tmp_path / "r.json"
    assert smoke.run(out) == 1
    assert "not found" in json.loads(out.read_text(encoding="utf-8"))["error"]


def test_the_engine_modules_import_here():
    assert smoke.missing_modules() == []


def test_a_missing_module_is_reported():
    missing = smoke.missing_modules(("json", "no_such_module_here"))
    assert len(missing) == 1 and missing[0].startswith("no_such_module_here: ModuleNotFoundError")


def test_a_bundle_missing_a_module_fails(fake_gui, monkeypatch, tmp_path):
    fake_gui(lambda script: True)
    monkeypatch.setattr(smoke, "missing_modules", lambda: ["pymupdf: ModuleNotFoundError"])
    out = tmp_path / "r.json"
    assert smoke.run(out) == 1
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["ready"] and result["shell"] and result["missing"] == ["pymupdf: ModuleNotFoundError"]