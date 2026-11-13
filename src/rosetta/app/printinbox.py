"""Print into Rosetta Plotter: the "Rosetta Plotter" printer (packaging/printer) writes each print as a
PDF to one fixed file, and this watches that file and hands every new print to the page as a drawing.

The printer is Windows' own "Microsoft Print To PDF" driver on a local port whose name is the file's
path, so printing asks no questions and writes straight there. The print spooler owns that file, so it
is never moved or deleted here: each new print is copied to the app's own folder and imported from the
copy (the next print overwrites the spooler's file).
"""
import logging
import os
import shutil
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

PRINT_FOLDER = "Rosetta Plotter/Print"  # under %ProgramData%; packaging/printer uses the same path
PRINT_FILE = "print.pdf"
POLL_S = 1.0
START_DELAY_S = 3.0  # the page needs a moment before it can take a dropped file
RECENT_S = 15 * 60  # a print made this long before the app opened is still imported
KEEP_COPIES = 20
_PDF_HEAD = b"%PDF-"
_PDF_TAIL = b"%%EOF"


def print_file() -> Path:
    """Where the Rosetta Plotter printer writes its PDF."""
    return Path(os.environ.get("ProgramData") or r"C:\ProgramData") / PRINT_FOLDER / PRINT_FILE


def is_finished_pdf(path: Path) -> bool:
    """True once the spooler has written the whole PDF (it grows the file as it prints)."""
    try:
        with open(path, "rb") as handle:
            if handle.read(len(_PDF_HEAD)) != _PDF_HEAD:
                return False
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 1024))
            return _PDF_TAIL in handle.read()
    except OSError:  # still being written, or gone
        return False


class PrintInbox:
    """Watches the printer's file; calls on_print([copy path]) for each new print."""

    def __init__(self, source: Path, copies: Path, on_print, clock=time.time, sleep=time.sleep):
        self._source = Path(source)
        self._copies = Path(copies)
        self._on_print = on_print
        self._clock = clock
        self._sleep = sleep
        self._seen: tuple[int, int] | None = None  # (modified time in ns, size) of the print last handled
        self._waiting: tuple[int, int] | None = None  # a print seen once: taken when it stops changing
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Begin watching. A print made shortly before the app opened is imported; older ones aren't."""
        stamp = self._stamp()
        if stamp is not None and self._clock() - stamp[0] / 1e9 > RECENT_S:
            self._seen = stamp
        self._thread = threading.Thread(target=self._watch, name="rosetta-print-inbox", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def check(self) -> Path | None:
        """One look at the printer's file. Returns the copy handed to the page, if a new print was ready.
        A print is taken on the second look that finds it unchanged and complete."""
        stamp = self._stamp()
        if stamp is None or stamp == self._seen:
            self._waiting = None
            return None
        if stamp != self._waiting or not is_finished_pdf(self._source):
            self._waiting = stamp
            return None
        try:
            copy = self._copy()
        except OSError:
            logger.info("Couldn't copy the print yet", exc_info=True)
            return None  # the spooler still has it: the next look tries again
        self._seen, self._waiting = stamp, None
        logger.info("A print arrived: %s", copy.name)
        self._on_print([str(copy)])
        return copy

    def _watch(self) -> None:
        if self._stop.wait(START_DELAY_S):
            return
        while not self._stop.is_set():
            try:
                self.check()
            except Exception:  # never let the watcher die: the next print should still arrive
                logger.exception("Checking for a print failed")
            self._stop.wait(POLL_S)

    def _stamp(self) -> tuple[int, int] | None:
        try:
            info = self._source.stat()
        except OSError:
            return None
        return (info.st_mtime_ns, info.st_size) if info.st_size > 0 else None

    def _copy(self) -> Path:
        self._copies.mkdir(parents=True, exist_ok=True)
        name = time.strftime("Print %Y-%m-%d %H.%M.%S", time.localtime(self._clock()))
        copy = self._copies / f"{name}.pdf"
        number = 2
        while copy.exists():
            copy = self._copies / f"{name} ({number}).pdf"
            number += 1
        shutil.copyfile(self._source, copy)
        self._tidy(keep=copy)
        return copy

    def _tidy(self, keep: Path) -> None:
        """Keep the newest few copies; older prints are already in the Jobs list or long forgotten."""
        try:
            copies = sorted(self._copies.glob("Print *.pdf"), key=lambda path: path.stat().st_mtime)
        except OSError:
            return
        for old in copies[:-KEEP_COPIES]:
            if old != keep:
                try:
                    old.unlink()
                except OSError:
                    pass
