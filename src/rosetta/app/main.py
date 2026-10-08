"""Start Rosetta Plotter: one WebView2 window (spec §6.5) showing the student page, with Api as its bridge.

Run `.venv\\Scripts\\rosetta-app` (no console window), or `.venv\\Scripts\\python -m rosetta.app.main`
to see Python's output while developing. Set ROSETTA_UI_URL=http://localhost:5173 to show Vite's dev
server instead of ui/dist, and ROSETTA_DEBUG=1 to allow WebView2's developer tools.
"""
import logging
import os
import sys
from pathlib import Path

import webview
from webview.dom import DOMEventHandler

from rosetta.app.api import ARTWORK_TYPES, Api
from rosetta.app.events import WindowSink
from rosetta.app.logs import setup_logging, stop_logging
from rosetta.app.settings import SettingsStore, app_folder
from rosetta.engine.options import ensure_std_streams

logger = logging.getLogger(__name__)

TITLE = "Rosetta Plotter"
START_SIZE = (1280, 800)
MIN_SIZE = (1024, 700)  # spec §6.5
BACKGROUND = "#1e1e1e"  # the window background (spec §3 --app-bg), shown while the page loads
DEV_URL_VARIABLE = "ROSETTA_UI_URL"
DEBUG_VARIABLE = "ROSETTA_DEBUG"
REPO_ROOT = Path(__file__).resolve().parents[3]  # src/rosetta/app/main.py -> the repository


def ui_entry() -> str | None:
    """The page to show: $ROSETTA_UI_URL, else ui/dist/index.html inside a PyInstaller bundle or in the
    repository. None until Plan 2b's page is built: the bridge console is shown instead."""
    dev_url = os.environ.get(DEV_URL_VARIABLE)
    if dev_url:
        return dev_url
    roots = [Path(sys._MEIPASS)] if hasattr(sys, "_MEIPASS") else []
    roots.append(REPO_ROOT)
    for root in roots:
        index = root / "ui" / "dist" / "index.html"
        if index.is_file():
            return str(index)
    return None


def console_html() -> str:
    return Path(__file__).with_name("console.html").read_text(encoding="utf-8")


def dropped_paths(event: dict) -> list[str]:
    """Full paths of the files dropped on the window. The page only sees names; pywebview adds each
    file's path as pywebviewFullPath."""
    files = event.get("dataTransfer", {}).get("files", [])
    return [file["pywebviewFullPath"] for file in files if file.get("pywebviewFullPath")]


def _accept_dropped_files(window, api: Api) -> None:
    def on_drop(event):
        paths = dropped_paths(event)
        if paths:
            api._files_dropped(paths)

    def allow_drop(_event):
        pass  # prevent_default on dragover is what lets a drop happen

    document = window.dom.document
    document.events.dragover += DOMEventHandler(allow_drop, True, True, debounce=500)
    document.events.drop += DOMEventHandler(on_drop, True, True)


def main() -> int:
    ensure_std_streams()
    log_path = setup_logging(app_folder() / "logs")
    logger.info("Rosetta Plotter starting")
    store = SettingsStore(app_folder() / "settings.json")
    sink = WindowSink()
    api = Api(store, sink, log_path=log_path)
    entry = ui_entry()
    window = webview.create_window(
        TITLE,
        url=entry,
        html=None if entry else console_html(),
        js_api=api,
        width=START_SIZE[0],
        height=START_SIZE[1],
        min_size=MIN_SIZE,
        background_color=BACKGROUND,
    )

    def choose_files():
        return window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True, file_types=ARTWORK_TYPES)

    api._attach_window(window, choose_files)  # main.py is the one place that wires Api to its window
    sink.attach(window.evaluate_js)
    window.events.closing += api._on_closing
    window.events.loaded += lambda: _accept_dropped_files(window, api)
    try:
        webview.start(gui="edgechromium", http_server=True, debug=bool(os.environ.get(DEBUG_VARIABLE)))
    finally:
        sink.close()
        logger.info("Rosetta Plotter closed")
        stop_logging()
    return 0


if __name__ == "__main__":
    sys.exit(main())
