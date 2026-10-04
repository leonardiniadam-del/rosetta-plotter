"""Keep Windows awake (system and display) while the current thread is plotting."""
import contextlib
import ctypes
import sys
import threading

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002  # students watch the screen while plotting

_depth = threading.local()  # SetThreadExecutionState is per thread, so nesting depth is too


def _kernel32():
    return ctypes.windll.kernel32


@contextlib.contextmanager
def keep_awake():
    """Re-entrant: only the outermost use on a thread sets and clears the execution state."""
    if sys.platform != "win32":
        yield
        return
    depth = getattr(_depth, "value", 0)
    if depth == 0:
        _kernel32().SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
    _depth.value = depth + 1
    try:
        yield
    finally:
        _depth.value -= 1
        if _depth.value == 0:
            _kernel32().SetThreadExecutionState(ES_CONTINUOUS)
