"""Start Rosetta Plotter: one WebView2 window (spec §6.5) showing the student page, with Api as its bridge.

Run `.venv\\Scripts\\rosetta-app` (no console window), or `.venv\\Scripts\\python -m rosetta.app.main`
to see Python's output while developing. Set ROSETTA_UI_URL=http://localhost:5173 to show Vite's dev
server instead of ui/dist, and ROSETTA_DEBUG=1 to allow WebView2's developer tools.

`--smoke-check <result-file>` opens the real window with a stand-in plotter (no serial port is ever
opened), checks the page comes up, writes a JSON result and closes (rosetta.app.smoke). The build
script uses it on the frozen app and the installed app.
"""
import logging
import os
import sys
from pathlib import Path

import webview
from webview.dom import DOMEventHandler

from rosetta.app import smoke
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


MAX_TAKEBACKS = 3  # in a row, without the app's page loading in between


class AppPageGuard:
    """pywebview hands the bridge (js_api) to any page the window shows. If the window ever leaves the
    app's own page (a link, or a file dropped where nothing catches it), take it back
    (plan2-notes "Lock navigation")."""

    def __init__(self, window):
        self._window = window
        self._home: str | None = None
        self._takebacks = 0

    def on_loaded(self) -> None:
        url = self._window.get_current_url()
        if not url:
            return
        page = url.split("#")[0].split("?")[0]
        if self._home is None:
            self._home = page
        elif page == self._home:
            self._takebacks = 0
        elif self._takebacks < MAX_TAKEBACKS:
            self._takebacks += 1
            logger.warning("The window left the app's page for %s; going back", url)
            self._window.load_url(self._home)
        elif self._takebacks == MAX_TAKEBACKS:
            self._takebacks += 1  # so the warning below is logged once
            logger.warning(
                "The window left the app's page for %s after %d take-backs in a row; giving up", url, MAX_TAKEBACKS
            )


def open_window(api: Api, sink: WindowSink, entry: str | None):
    """Create the app's one window and wire it to the bridge. Shared by the app and its smoke check
    (rosetta.app.smoke), so the check exercises the same wiring the students get."""
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
    if entry:
        window.events.loaded += AppPageGuard(window).on_loaded
    return window


def start_gui(func=None) -> None:
    webview.start(func, gui="edgechromium", http_server=True, debug=bool(os.environ.get(DEBUG_VARIABLE)))


def main(argv: list[str] | None = None) -> int:
    ensure_std_streams()
    argv = sys.argv[1:] if argv is None else argv
    try:
        smoke_result = smoke.result_path(argv)
    except smoke.UsageError:
        return 2
    if smoke_result is not None:
        return smoke.run(smoke_result)
    log_path = setup_logging(app_folder() / "logs")
    logger.info("Rosetta Plotter starting")
    store = SettingsStore(app_folder() / "settings.json")
    sink = WindowSink()
    api = Api(store, sink, log_path=log_path)
    open_window(api, sink, ui_entry())
    try:
        start_gui()
    finally:
        sink.close()
        logger.info("Rosetta Plotter closed")
        stop_logging()
    return 0


if __name__ == "__main__":
    sys.exit(main())
