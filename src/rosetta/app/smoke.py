"""`--smoke-check <result-file>`: open the real window for a moment, check the page came up, write the
answer as JSON and close. The build script runs it on the frozen app (scripts/build_installer.ps1); it
is safe on a laptop with a plotter plugged in.

Never touches hardware, twice over: the Machine gets a stand-in plotter (NoPlotter) instead of the EMS
one, and every way plotink/pyserial could list, find or open a serial port is switched off for the
whole process (no_serial_ports), so even a stray call can't reach a real AxiDraw.

The result file holds {"ready": bool, "shell": bool, "version": str, "error": str|null, "seconds": float};
the process exits 0 only when ready and shell are both true.
"""
import json
import os
import tempfile
import threading
import time
from pathlib import Path

import rosetta

FLAG = "--smoke-check"
TIMEOUT_S = 30.0
EXIT_GRACE_S = 15.0  # after the timeout, how long the window gets to close before the process is ended
SHELL_RENDERED = """(() => { const app = document.querySelector("rp-app"); const root = app && app.shadowRoot;
  return !!(root && root.querySelector("rp-plate") && root.querySelector("rp-menubar")); })()"""

# Everything in plotink.ebb_serial that lists, finds or opens serial ports (the same list as tests/conftest.py).
PORT_SEARCHES = (
    "findPort", "find_named_ebb", "listEBBports", "list_port_info", "list_named_ebbs",
    "openPort", "open_named_port", "testPort",
)


class UsageError(Exception):
    pass


def result_path(argv: list[str]) -> Path | None:
    """The result file named by `--smoke-check <file>` (or `--smoke-check=<file>`), else None."""
    for index, arg in enumerate(argv):
        if arg == FLAG:
            if index + 1 >= len(argv) or not argv[index + 1] or argv[index + 1].startswith("--"):
                raise UsageError(f"{FLAG} needs a result file")
            return Path(argv[index + 1])
        if arg.startswith(FLAG + "="):
            value = arg[len(FLAG) + 1:]
            if not value:
                raise UsageError(f"{FLAG} needs a result file")
            return Path(value)
    return None


class NoPlotter:
    """Stands in for the plotter: the smoke check must never touch hardware."""

    def connect(self, settings) -> bool:
        return False

    def disconnect(self) -> None:
        pass

    def request_pause(self) -> None:
        pass


def no_serial_ports() -> None:
    """Switch off every way this process could list, find or open a serial port. For the smoke check only:
    the process ends when the check does."""
    import serial
    from plotink import ebb_serial

    def finds_nothing(*args, **kwargs):
        return None

    def refuses(*args, **kwargs):
        raise serial.SerialException("The smoke check may not open a serial port")

    for name in PORT_SEARCHES:
        setattr(ebb_serial, name, finds_nothing)
    ebb_serial.comports = lambda *args, **kwargs: []
    serial.Serial = refuses


def make_api(folder: Path):
    """An Api with throwaway settings and the stand-in plotter."""
    from rosetta.app.api import Api
    from rosetta.app.events import WindowSink
    from rosetta.app.machine import Machine
    from rosetta.app.settings import SettingsStore

    store = SettingsStore(folder / "settings.json")
    sink = WindowSink()
    return Api(store, sink, machine=Machine(store, plotter_factory=NoPlotter)), sink


def write_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def passed(result: dict) -> bool:
    return bool(result.get("ready")) and bool(result.get("shell"))


def run(path: Path, timeout_s: float = TIMEOUT_S) -> int:
    from rosetta.app import main

    no_serial_ports()
    started = time.monotonic()
    result = {"ready": False, "shell": False, "version": rosetta.__version__, "error": None, "seconds": 0.0}
    written = threading.Event()
    lock = threading.Lock()

    def finish(error: str | None = None) -> None:
        with lock:
            if written.is_set():
                return
            if error and not result["error"]:
                result["error"] = error
            result["seconds"] = round(time.monotonic() - started, 2)
            write_result(path, result)
            written.set()

    def watchdog() -> None:
        # The window never came up (WebView2 missing, a hang): write the failure, then end the process.
        if written.wait(timeout_s + EXIT_GRACE_S):
            return
        finish(f"timed out after {timeout_s:.0f} s")
        os._exit(1)

    threading.Thread(target=watchdog, daemon=True).start()

    entry = main.ui_entry()
    if not entry:
        finish("ui/dist/index.html was not found")
        return 1
    api, sink = make_api(Path(tempfile.mkdtemp(prefix="rosetta-smoke-")))
    window = main.open_window(api, sink, entry)

    def check() -> None:
        try:
            deadline = started + timeout_s
            while time.monotonic() < deadline and not result["ready"]:
                result["ready"] = window.evaluate_js("window.rosettaReady === true") is True
                if not result["ready"]:
                    time.sleep(0.25)
            while time.monotonic() < deadline and not result["shell"]:
                result["shell"] = window.evaluate_js(SHELL_RENDERED) is True
                if not result["shell"]:
                    time.sleep(0.25)
            if not passed(result):
                finish(f"the page wasn't ready within {timeout_s:.0f} s")
        except Exception as error:  # report it in the result file rather than lose it
            finish(f"{type(error).__name__}: {error}")
        finally:
            finish()
            window.destroy()

    try:
        main.start_gui(check)
    except Exception as error:
        finish(f"{type(error).__name__}: {error}")
    finally:
        sink.close()
    finish("the window closed before the check finished")
    return 0 if passed(result) else 1
