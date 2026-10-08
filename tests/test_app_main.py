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


def test_the_window_is_taken_back_only_three_times_in_a_row(caplog):
    window = _Window()
    guard = main.AppPageGuard(window)
    window.url = "http://127.0.0.1:5000/index.html"
    guard.on_loaded()
    # The app's page itself fails to load, so every take-back lands on an error page.
    window.url = "chrome-error://chromewebdata/"
    with caplog.at_level("WARNING", logger=main.logger.name):
        for _ in range(6):
            guard.on_loaded()
    assert window.loaded == ["http://127.0.0.1:5000/index.html"] * 3
    stopped = [r for r in caplog.records if "giving up" in r.getMessage()]
    assert len(stopped) == 1


def test_a_good_load_of_the_app_page_resets_the_take_back_count():
    window = _Window()
    guard = main.AppPageGuard(window)
    home = "http://127.0.0.1:5000/index.html"
    window.url = home
    guard.on_loaded()
    for _ in range(2):
        window.url = "file:///C:/Users/student/drawing.svg"
        guard.on_loaded()
    window.url = home
    guard.on_loaded()  # the take-back worked
    for _ in range(3):
        window.url = "file:///C:/Users/student/drawing.svg"
        guard.on_loaded()
    assert window.loaded == [home] * 5
    window.url = "file:///C:/Users/student/drawing.svg"
    guard.on_loaded()
    assert window.loaded == [home] * 5
