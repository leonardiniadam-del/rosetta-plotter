"""Open the real Rosetta window for a moment, check it works, then close it.

    .venv\\Scripts\\python scripts\\smoke_window.py          the bridge console: Python <-> page both ways
    .venv\\Scripts\\python scripts\\smoke_window.py --page   the built student page (run `npm run build` in ui\\ first)

Not part of pytest: it needs a desktop session and WebView2. The page check uses a stand-in plotter,
so it never touches a real one even if it's plugged in.
"""
import sys
import tempfile
import time
from pathlib import Path

import webview

from rosetta.app.api import Api
from rosetta.app.events import WindowSink
from rosetta.app.machine import Machine
from rosetta.app.main import REPO_ROOT, console_html
from rosetta.app.settings import SettingsStore

READY_TIMEOUT_S = 15.0


class _NoPlotter:
    """Stands in for the plotter: this check must never touch hardware."""

    def connect(self, settings) -> bool:
        return False

    def disconnect(self) -> None:
        pass

    def request_pause(self) -> None:
        pass


def _api() -> tuple[Api, WindowSink]:
    store = SettingsStore(Path(tempfile.mkdtemp()) / "settings.json")
    sink = WindowSink()
    return Api(store, sink, machine=Machine(store, plotter_factory=_NoPlotter)), sink


def check_console() -> bool:
    api, sink = _api()
    window = webview.create_window("Rosetta smoke test", html=console_html(), js_api=api)
    sink.attach(window.evaluate_js)
    seen = {}

    def check():
        try:
            seen["methods"] = window.evaluate_js("Object.keys(window.pywebview.api).length")
            sink.emit("smoke", {"hello": "page"})
            time.sleep(1)
            seen["events"] = window.evaluate_js("document.getElementById('events').textContent")
        finally:
            window.destroy()

    webview.start(check, gui="edgechromium", http_server=True)
    sink.close()
    expected = len([name for name in dir(api) if not name.startswith("_")])
    passed = seen.get("methods") == expected and "smoke" in (seen.get("events") or "")
    print(seen)
    print("PASS" if passed else f"FAIL (expected {expected} methods and a smoke event)")
    return passed


def check_page() -> bool:
    index = REPO_ROOT / "ui" / "dist" / "index.html"
    if not index.is_file():
        print("FAIL (ui\\dist\\index.html is missing: run `npm run build` in ui\\ first)")
        return False
    api, sink = _api()
    window = webview.create_window("Rosetta smoke test (page)", url=str(index), js_api=api, width=1280, height=800)
    sink.attach(window.evaluate_js)
    seen = {}

    def check():
        try:
            deadline = time.monotonic() + READY_TIMEOUT_S
            while time.monotonic() < deadline and not seen.get("ready"):
                seen["ready"] = window.evaluate_js("window.rosettaReady === true")
                time.sleep(0.25)
            seen["shell"] = window.evaluate_js("document.querySelector('rp-app') !== null")
            seen["text"] = window.evaluate_js("document.body.innerText.slice(0, 120)")
        finally:
            window.destroy()

    webview.start(check, gui="edgechromium", http_server=True)
    sink.close()
    passed = bool(seen.get("ready")) and bool(seen.get("shell"))
    print(seen)
    print("PASS" if passed else "FAIL (the page didn't report itself ready)")
    return passed


if __name__ == "__main__":
    sys.exit(0 if (check_page() if "--page" in sys.argv[1:] else check_console()) else 1)
