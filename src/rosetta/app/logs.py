"""The app's log file and the "Copy diagnostics" text (spec §10)."""
import logging
import platform
import sys
from collections import deque
from importlib.metadata import PackageNotFoundError, version
from logging.handlers import RotatingFileHandler
from pathlib import Path

import rosetta

LOG_NAME = "rosetta.log"
MAX_BYTES = 1_000_000
BACKUPS = 3
DIAGNOSTIC_LINES = 200
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_LOGGERS = ("rosetta", "pywebview")  # rosetta.ems (EMS's own messages) is under rosetta
_OWNED = "_rosetta_app_log"
_PREVIOUS_LEVEL = "_rosetta_previous_level"  # the rosetta logger's level before setup_logging


class _QuietLibraries(logging.Filter):
    """Everything from Rosetta; only warnings and errors from pywebview."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith("rosetta") or record.levelno >= logging.WARNING


def setup_logging(folder: Path) -> Path | None:
    """Log to folder/rosetta.log (1 MB, 3 old files kept). Returns its path, or None if the folder
    can't be written (the app still runs). Calling it again replaces the earlier log handler."""
    stop_logging()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            folder / LOG_NAME, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8"
        )
    except OSError:
        return None
    rosetta_logger = logging.getLogger("rosetta")
    setattr(handler, _OWNED, True)
    setattr(handler, _PREVIOUS_LEVEL, rosetta_logger.level)
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(_QuietLibraries())
    rosetta_logger.setLevel(logging.INFO)
    for name in _LOGGERS:
        logging.getLogger(name).addHandler(handler)
    return Path(handler.baseFilename)


def stop_logging() -> None:
    """Remove and close the handler setup_logging added (flushing the file), and put the rosetta
    logger's level back."""
    closed = set()
    for name in _LOGGERS:
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            if getattr(handler, _OWNED, False):
                logger.removeHandler(handler)
                if name == "rosetta":
                    logger.setLevel(getattr(handler, _PREVIOUS_LEVEL, logger.level))
                if id(handler) not in closed:
                    handler.close()
                    closed.add(id(handler))


def diagnostics(log_path: Path | None, extra: dict[str, str]) -> str:
    """Versions, the given extra lines (plotter, plot state...), then the end of the log."""
    lines = [
        f"Rosetta Plotter {rosetta.__version__}",
        f"Windows: {platform.platform()}",
        f"Python: {sys.version.split()[0]}",
        f"pywebview: {_version('pywebview')}",
        f"AxiDraw engine: {_version('axidrawinternal')}",
    ]
    lines += [f"{key}: {value}" for key, value in extra.items()]
    lines.append("")
    if log_path is None:
        lines.append("(No log file: the log folder couldn't be written.)")
    else:
        lines.append(f"Last lines of {log_path}:")
        lines += _tail(Path(log_path), DIAGNOSTIC_LINES)
    return "\n".join(lines)


def _version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not installed"


def _tail(path: Path, count: int) -> list[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return [line.rstrip("\n") for line in deque(handle, maxlen=count)]
    except OSError:
        return ["(The log file couldn't be read.)"]
