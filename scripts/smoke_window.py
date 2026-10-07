"""Open the real Rosetta window for a moment and check the bridge works both ways, then close it.

Not part of pytest (it needs a desktop session and WebView2). Run:
    .venv\\Scripts\\python scripts\\smoke_window.py
"""
import sys
import tempfile
import time
from pathlib import Path

import webview

from rosetta.app.api import Api
from rosetta.app.events import WindowSink
from rosetta.app.main import console_html
from rosetta.app.settings import SettingsStore


def main() -> int:
    sink = WindowSink()
    api = Api(SettingsStore(Path(tempfile.mkdtemp()) / "settings.json"), sink)
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
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
