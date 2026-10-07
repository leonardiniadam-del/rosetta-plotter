import logging

import pytest

import rosetta
from rosetta.app.logs import BACKUPS, MAX_BYTES, diagnostics, setup_logging, stop_logging


@pytest.fixture(autouse=True)
def leave_logging_as_it_was():
    yield
    stop_logging()


def test_the_log_keeps_rosetta_and_engine_messages(tmp_path):
    path = setup_logging(tmp_path / "logs")
    logging.getLogger("rosetta.app.example").info("hello from rosetta")
    logging.getLogger("rosetta.ems").info("engine says hi")
    logging.getLogger("pywebview").info("library chatter")
    logging.getLogger("pywebview").warning("pywebview trouble")
    stop_logging()
    text = path.read_text(encoding="utf-8")
    assert "hello from rosetta" in text
    assert "engine says hi" in text
    assert "pywebview trouble" in text
    assert "library chatter" not in text


def test_setting_up_twice_does_not_write_lines_twice(tmp_path):
    setup_logging(tmp_path / "logs")
    path = setup_logging(tmp_path / "logs")
    logging.getLogger("rosetta").info("once")
    stop_logging()
    assert path.read_text(encoding="utf-8").count("once") == 1


def test_stopping_puts_the_rosetta_level_back(tmp_path):
    rosetta_logger = logging.getLogger("rosetta")
    before = rosetta_logger.level
    rosetta_logger.setLevel(logging.WARNING)
    try:
        setup_logging(tmp_path / "logs")
        assert rosetta_logger.level == logging.INFO
        stop_logging()
        assert rosetta_logger.level == logging.WARNING
    finally:
        rosetta_logger.setLevel(before)


def test_the_log_rotates(tmp_path):
    setup_logging(tmp_path / "logs")
    handlers = [h for h in logging.getLogger("rosetta").handlers if hasattr(h, "maxBytes")]
    assert [(h.maxBytes, h.backupCount) for h in handlers] == [(MAX_BYTES, BACKUPS)]


def test_an_unwritable_folder_means_no_log_file(tmp_path):
    blocker = tmp_path / "a file"
    blocker.write_text("x", encoding="utf-8")
    assert setup_logging(blocker / "logs") is None


def test_diagnostics_has_versions_details_and_the_last_lines(tmp_path):
    log = tmp_path / "rosetta.log"
    log.write_text("".join(f"line {number:03d}\n" for number in range(300)), encoding="utf-8")
    text = diagnostics(log, {"Plotter": "AxiDraw SE/A1"})
    assert f"Rosetta Plotter {rosetta.__version__}" in text
    assert "Plotter: AxiDraw SE/A1" in text
    assert "line 299" in text and "line 100" in text
    assert "line 099" not in text


def test_diagnostics_without_a_log_file_says_so():
    assert "No log file" in diagnostics(None, {})
