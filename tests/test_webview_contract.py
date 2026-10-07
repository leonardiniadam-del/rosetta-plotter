"""Everything Rosetta Plotter uses from pywebview, checked in one place (like test_engine_contract.py).

If this fails after a pywebview update, read the new pywebview source before changing any Rosetta code.
"""
import inspect
from importlib.metadata import version

import webview
from webview import util
from webview.dom import DOMEventHandler
from webview.window import Window


def test_pywebview_version_is_pinned():
    assert version("pywebview") == "6.2.1"


def test_window_functions_used_by_main():
    for name in ("create_file_dialog", "evaluate_js", "destroy"):
        assert callable(getattr(Window, name))
    assert webview.FileDialog.OPEN == 10
    window_parameters = inspect.signature(webview.create_window).parameters
    for name in ("url", "html", "js_api", "width", "height", "min_size", "background_color"):
        assert name in window_parameters
    start_parameters = inspect.signature(webview.start).parameters
    for name in ("gui", "http_server", "debug"):
        assert name in start_parameters


def test_closing_event_can_cancel_the_close():
    # Event(self, True) runs handlers synchronously, and a handler returning False cancels closing.
    assert "self.events.closing = Event(self, True)" in inspect.getsource(Window.__init__)


def test_dropped_files_carry_their_full_path():
    assert list(inspect.signature(DOMEventHandler).parameters)[:3] == [
        "callback", "prevent_default", "stop_propagation",
    ]
    assert "pywebviewFullPath" in inspect.getsource(util)


def test_only_public_names_are_exposed_to_the_page():
    # Api keeps all its state in underscore names; pywebview skips those when exposing js_api.
    assert "if name.startswith('_'):" in inspect.getsource(util)
