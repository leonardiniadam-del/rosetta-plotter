"""Messages from Python to the page (spec §6.5): plot states, live progress, dropped files.

The page defines window.rosettaEvent(name, data). Sending never blocks the caller: a plot's progress
callback runs on the engine's poller thread, and a slow page must not slow the plot (plan2-notes.md).
While progress messages wait to be sent, only the newest is kept.
"""
import json
import logging
import threading
from collections import deque

logger = logging.getLogger(__name__)

COALESCED = frozenset({"plot_progress"})


class RecordingSink:
    """For tests: keeps every event."""

    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def emit(self, name: str, data: dict) -> None:
        self.events.append((name, data))

    def named(self, name: str) -> list[dict]:
        return [data for event, data in self.events if event == name]


class WindowSink:
    def __init__(self, run_js=None):
        self._run_js = run_js  # window.evaluate_js, once the window exists
        self._queue: deque[tuple[str, dict]] = deque()
        self._wake = threading.Condition()
        self._closed = False
        self._thread = threading.Thread(target=self._send_loop, name="rosetta-events", daemon=True)
        self._thread.start()

    def attach(self, run_js) -> None:
        with self._wake:
            self._run_js = run_js
            self._wake.notify()

    def emit(self, name: str, data: dict) -> None:
        with self._wake:
            if name in COALESCED:
                for index, (waiting, _old) in enumerate(self._queue):
                    if waiting == name:
                        self._queue[index] = (name, data)
                        return
            self._queue.append((name, data))
            self._wake.notify()

    def close(self, timeout: float = 2.0) -> None:
        with self._wake:
            self._closed = True
            self._wake.notify()
        self._thread.join(timeout)

    def _send_loop(self) -> None:
        while True:
            with self._wake:
                while not self._closed and (self._run_js is None or not self._queue):
                    self._wake.wait()
                if self._closed:
                    return
                name, data = self._queue.popleft()
                run_js = self._run_js
            script = f"window.rosettaEvent && window.rosettaEvent({json.dumps(name)}, {json.dumps(data)})"
            try:
                run_js(script)
            except Exception:  # the page may be reloading; the next event will try again
                logger.warning("Couldn't send %s to the page", name, exc_info=True)
