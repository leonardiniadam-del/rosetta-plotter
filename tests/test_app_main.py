import sys

from rosetta.app import main


def test_the_dev_server_wins(monkeypatch):
    monkeypatch.setenv(main.DEV_URL_VARIABLE, "http://localhost:5173")
    assert main.ui_entry() == "http://localhost:5173"


def test_a_bundled_page_is_found(monkeypatch, tmp_path):
    monkeypatch.delenv(main.DEV_URL_VARIABLE, raising=False)
    index = tmp_path / "ui" / "dist" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert main.ui_entry() == str(index)


def test_the_console_is_shown_until_the_page_is_built(monkeypatch, tmp_path):
    monkeypatch.delenv(main.DEV_URL_VARIABLE, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(main, "REPO_ROOT", tmp_path)
    assert main.ui_entry() is None
    assert "window.rosettaEvent" in main.console_html()


def test_dropped_files_give_their_full_paths():
    event = {"dataTransfer": {"files": [
        {"name": "a.svg", "pywebviewFullPath": "C:\\art\\a.svg"},
        {"name": "b.svg"},  # pywebview couldn't match this one to a path
    ]}}
    assert main.dropped_paths(event) == ["C:\\art\\a.svg"]
    assert main.dropped_paths({}) == []


class _Window:
    def __init__(self):
        self.url = None
        self.loaded = []

    def get_current_url(self):
        return self.url

    def load_url(self, url):
        self.loaded.append(url)


def test_the_window_goes_back_to_the_app_page():
    window = _Window()
    guard = main.AppPageGuard(window)
    window.url = "http://127.0.0.1:5000/index.html"
    guard.on_loaded()
    window.url = "http://127.0.0.1:5000/index.html#settings"
    guard.on_loaded()
    assert window.loaded == []
    window.url = "file:///C:/Users/student/drawing.svg"
    guard.on_loaded()
    assert window.loaded == ["http://127.0.0.1:5000/index.html"]
