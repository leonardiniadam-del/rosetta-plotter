import threading
import time

from rosetta.app.events import RecordingSink, WindowSink


def _wait(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.005)


def test_events_wait_for_the_page_then_go_in_order():
    sent = []
    sink = WindowSink()
    sink.emit("plot_state", {"state": "ready"})
    sink.emit("files_dropped", {"paths": ["C:\\a.svg"]})
    time.sleep(0.05)
    assert sent == []  # no page yet
    sink.attach(sent.append)
    _wait(lambda: len(sent) == 2)
    sink.close()
    assert sent[0] == 'window.rosettaEvent && window.rosettaEvent("plot_state", {"state": "ready"})'
    assert '"files_dropped"' in sent[1] and '"C:\\\\a.svg"' in sent[1]


def test_waiting_progress_is_replaced_by_the_newest():
    sent, release = [], threading.Event()

    def slow_page(script):
        sent.append(script)
        release.wait(5)

    sink = WindowSink(slow_page)
    sink.emit("plot_state", {"state": "plotting"})
    _wait(lambda: len(sent) == 1)  # the page is busy with the first event
    for number in range(5):
        sink.emit("plot_progress", {"fraction": number / 4})
    sink.emit("plot_state", {"state": "done"})
    release.set()
    _wait(lambda: len(sent) == 3)
    sink.close()
    assert '"fraction": 1.0' in sent[1] and '"done"' in sent[2]


def test_emit_never_waits_for_the_page():
    release = threading.Event()
    sink = WindowSink(lambda script: release.wait(5))
    started = time.monotonic()
    for number in range(100):
        sink.emit("plot_progress", {"fraction": number})
    assert time.monotonic() - started < 0.5
    release.set()
    sink.close()


def test_a_page_error_does_not_stop_later_events():
    sent = []

    def flaky_page(script):
        if not sent:
            sent.append("failed")
            raise RuntimeError("page not ready")
        sent.append(script)

    sink = WindowSink(flaky_page)
    sink.emit("first", {})
    sink.emit("second", {})
    _wait(lambda: len(sent) == 2)
    sink.close()
    assert '"second"' in sent[1]


def test_recording_sink_for_tests():
    sink = RecordingSink()
    sink.emit("x", {"n": 1})
    sink.emit("y", {})
    sink.emit("x", {"n": 2})
    assert sink.named("x") == [{"n": 1}, {"n": 2}]
