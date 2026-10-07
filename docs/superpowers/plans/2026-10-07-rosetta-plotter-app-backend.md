# Rosetta Plotter App Backend (Plan 2a of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build everything the student app's page will call. That means a fully tested Python app layer (settings, logs, session, plotter owner, plot controller, the pywebview bridge) and a WebView2 window that opens a bare "bridge console" page, so the app can be driven end to end before the real screens exist.

**Architecture:**
- A new `src/rosetta/app/` package sits on top of the finished Plan 1 core.
- `Machine` is the single owner of the plotter connection: connect, identify, home, jog, pen, trace, and handing the port to plot runs.
- `PlotController` is the Step 5 state machine. It handles pen changes, pause, resume, Return Home, lost cables and re-homing.
- `Api` is the pywebview `js_api`. Every public method returns `{"ok": true, ...}` or `{"ok": false, "message", "details"}`.
- Python pushes events to the page through a non-blocking `WindowSink`.
- The animated preview path comes from recording the EMS engine's own planned moves (new `engine/preview.py`).

**Tech Stack:** Python 3.12 (`.venv`), the Plan 1 core, EMS AxiDraw API 3.9.6, pywebview 6.2.1 (Edge WebView2 backend, pythonnet), pytest. All commands use Windows PowerShell.

**Spec:** `docs/superpowers/specs/2026-10-03-rosetta-plotter-design.md` (§5, §6.1, §6.4, §6.5, §8, §10)
**Review notes this plan answers:** `docs/superpowers/plan2-notes.md`

**Why Plan 2 is split in two:**
- **Plan 2a (this plan)** is the Python side of the app.
- **Plan 2b** covers the student screens: the TypeScript/Vite front end, the Rhino-style canvas, the five steps, and dialogs. It's written after this plan is done, against the bridge as built and reviewed here, the same way Plan 2 waited for Plan 1.
- Task 15 writes `docs/bridge.md`, the contract Plan 2b builds on.
- **Plan 3** covers the installer and release.

**Conventions for every task:**
- Run all commands from the repo root `C:\Users\leona\Projects\rosetta-plotter` in PowerShell.
- Tests run with `.venv\Scripts\python -m pytest`. The full suite must stay green after every task (501 tests at the start).
- Every commit ends with the trailer `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
- Student-facing text follows the spec's wording rule. It never says top, bottom, upper or lower for corners. It names the HOME label and the USB port.
- No test may reach a real plotter. `tests/conftest.py` already blocks every serial port, so tests use the fakes in `tests/fake_ebb.py`.
- When reading or writing files with PowerShell, always pass `-Encoding UTF8`.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Adds `pywebview==6.2.1` and the `rosetta-app` GUI entry point |
| `src/rosetta/errors.py` | Adds `UserProblem` (plain-language message + optional details) |
| `src/rosetta/engine/options.py` | Adds `Advanced` engine options and their validation |
| `src/rosetta/engine/runner.py` | Splits `estimate()` into a reusable `dry_run()` |
| `src/rosetta/engine/preview.py` | `plan_layer()`: the pen's planned path, in order, with times |
| `src/rosetta/engine/plotter.py` | Adds `port_name()` |
| `src/rosetta/loader.py` | `Artwork.preview_svg`: the normalized drawing, for the canvas |
| `src/rosetta/app/__init__.py` | Package docstring |
| `src/rosetta/app/paper.py` | Paper presets and orientation |
| `src/rosetta/app/settings.py` | `%APPDATA%\RosettaPlotter\settings.json`, never fails to load |
| `src/rosetta/app/logs.py` | Rotating log file and the Copy-diagnostics text |
| `src/rosetta/app/session.py` | The paper and the pieces of artwork on it |
| `src/rosetta/app/payloads.py` | Rosetta objects → plain JSON for the page |
| `src/rosetta/app/machine.py` | The one owner of the plotter connection |
| `src/rosetta/app/events.py` | Python → page events, never blocking the caller |
| `src/rosetta/app/plotjob.py` | Step 5 state machine: prepare, trace, plot, pause, resume, re-home |
| `src/rosetta/app/api.py` | The pywebview `js_api` the page calls |
| `src/rosetta/app/main.py` | The window: page location, file drops, closing mid-plot |
| `src/rosetta/app/console.html` | Bridge console, shown until Plan 2b's page is built |
| `scripts/smoke_window.py` | Opens the real window for a second to check the bridge both ways (not pytest) |
| `docs/bridge.md` | Every bridge method and event, for Plan 2b |
| `tests/app_helpers.py` | `Bench` (pluggable fake plotter), `make_machine`, `wait_for` |
| `tests/test_webview_contract.py` | Everything used from pywebview, pinned |

---

### Task 1: pywebview dependency, the `rosetta.app` package, and its contract test

**Files:**
- Modify: `pyproject.toml`
- Create: `src/rosetta/app/__init__.py`, `tests/test_webview_contract.py`

- [ ] **Step 1: Write the failing contract test**

`tests/test_webview_contract.py`:
```python
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
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python -m pytest tests\test_webview_contract.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'webview'`.

- [ ] **Step 3: Add the dependency and entry point**

In `pyproject.toml`, change the dependency list to:
```toml
dependencies = [
    "lxml>=5.0",
    "tinycss2>=1.3",
    "pymupdf>=1.24",
    "pywebview==6.2.1",
]
```
and add this section right after `[project.scripts]`:
```toml
[project.gui-scripts]
rosetta-app = "rosetta.app.main:main"
```

Create `src/rosetta/app/__init__.py`:
```python
"""The student app (spec §5, §6.4, §6.5): settings, session, plotter owner, plot controller, and the
bridge the WebView2 page calls."""
```

Install:
```powershell
.venv\Scripts\python -m pip install -c constraints.txt -e ".[dev]"
```
Expected: `Successfully installed ... pywebview-6.2.1 pythonnet-3.x ...` (`bottle`, `proxy_tools`, `clr_loader` and `typing_extensions` come along).

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_webview_contract.py -v`
Expected: `5 passed`.
Run: `.venv\Scripts\python -m pytest -q`
Expected: `506 passed`.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml src\rosetta\app\__init__.py tests\test_webview_contract.py
git commit -m "build: add pywebview 6.2.1 and the rosetta.app package" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Advanced engine options

The spec's "Advanced" links lead to speeds, acceleration, pen timing, optimization and resolution (§5). They become one frozen `Advanced` value inside `PlotSettings`. It replaces the old `reordering` and `hiding` fields, which nothing outside `options.py` set. Validation happens before the engine sees anything, as `plan2-notes.md` asks ("Validate before calling the engine").

**Files:**
- Modify: `src/rosetta/engine/options.py` (whole file below)
- Test: `tests/test_engine_options.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_engine_options.py`:
```python
from types import SimpleNamespace

from rosetta.engine.options import Advanced, MIN_PEN_TRAVEL, advanced_from_dict


def _options_after(settings):
    ad = SimpleNamespace(options=SimpleNamespace())
    apply_settings(ad, settings)
    return ad.options


def test_advanced_options_reach_the_engine():
    advanced = Advanced(
        pen_up=90, speed_pendown=40, speed_penup=60, accel=50, pen_rate_raise=80,
        pen_rate_lower=30, pen_delay_up=100, pen_delay_down=200, reordering=4,
        hiding=True, resolution=2,
    )
    o = _options_after(PlotSettings(model=1, pen_down=30, advanced=advanced))
    assert (o.pen_pos_up, o.speed_pendown, o.speed_penup, o.accel) == (90, 40, 60, 50)
    assert (o.pen_rate_raise, o.pen_rate_lower, o.pen_delay_up, o.pen_delay_down) == (80, 30, 100, 200)
    assert (o.reordering, o.hiding, o.resolution) == (4, True, 2)


def test_without_overrides_the_pen_type_sets_the_speed():
    o = _options_after(PlotSettings(model=1, pen_type="brush"))
    assert (o.speed_pendown, o.speed_penup, o.pen_pos_up, o.accel, o.resolution) == (12, 75, 60, 75, 1)


def test_an_advanced_pen_up_height_overrides_the_automatic_one():
    assert PlotSettings(model=1, pen_down=30, advanced=Advanced(pen_up=45)).pen_up == 45


def test_an_advanced_pen_up_height_must_clear_pen_down():
    settings = PlotSettings(model=1, pen_down=50, advanced=Advanced(pen_up=50 + MIN_PEN_TRAVEL - 1))
    with pytest.raises(ValueError, match="at least 10 above"):
        _options_after(settings)


@pytest.mark.parametrize("values, message", [
    ({"accel": 0}, "Acceleration must be from 1 to 100"),
    ({"reordering": 3}, "Path order must be one of 0, 1, 2, 4"),
    ({"pen_delay_up": -5}, "from 0 to 1000"),
    ({"speed_penup": 50.5}, "whole number"),
    ({"accel": True}, "whole number"),
    ({"hiding": 1}, "on or off"),
    ({"warp": 9}, "Unknown advanced option: warp"),
])
def test_advanced_from_dict_rejects_bad_values(values, message):
    with pytest.raises(ValueError, match=message):
        advanced_from_dict(values)


def test_advanced_from_dict_accepts_none_for_the_automatic_values():
    assert advanced_from_dict({"pen_up": None, "speed_pendown": None, "accel": 60}) == Advanced(accel=60)


def test_apply_settings_checks_advanced_values_too():
    with pytest.raises(ValueError, match="Acceleration"):
        _options_after(PlotSettings(model=1, advanced=Advanced(accel=500)))
```
(`pytest`, `PlotSettings` and `apply_settings` are already imported at the top of this file.)

- [ ] **Step 2: Run them to make sure they fail**

Run: `.venv\Scripts\python -m pytest tests\test_engine_options.py -v`
Expected: collection error, `ImportError: cannot import name 'Advanced'`.

- [ ] **Step 3: Rewrite `src/rosetta/engine/options.py`**

```python
"""Rosetta's plot settings, and how they map onto EMS pyaxidraw options."""
import dataclasses
import logging
import os
import sys
from dataclasses import dataclass, field

from rosetta.models import MODELS, PEN_TYPES, PEN_UP_SPEED

PEN_DOWN_MAX = 80  # keeps at least 20% of servo travel between pen down and pen up
MIN_PEN_TRAVEL = 10  # an Advanced pen-up height must be at least this far above pen-down


@dataclass(frozen=True)
class Advanced:
    """Engine options a student only sees under "Advanced" (spec §5). None means Rosetta decides."""

    pen_up: int | None = None  # percent; None = max(60, pen-down + 20), capped at 100
    speed_pendown: int | None = None  # percent of maximum; None = the pen type's speed
    speed_penup: int = PEN_UP_SPEED
    accel: int = 75
    pen_rate_raise: int = 75
    pen_rate_lower: int = 50
    pen_delay_up: int = 0  # ms
    pen_delay_down: int = 0  # ms
    reordering: int = 2  # 0 join nearby ends only, 1 reorder, 2 reorder and reverse, 4 keep file order
    hiding: bool = False  # hidden-line removal
    resolution: int = 1  # 1 fine, 2 coarse (faster)


ADVANCED_LABELS = {
    "pen_up": "Pen-up height",
    "speed_pendown": "Pen-down speed",
    "speed_penup": "Pen-up speed",
    "accel": "Acceleration",
    "pen_rate_raise": "Pen raising speed",
    "pen_rate_lower": "Pen lowering speed",
    "pen_delay_up": "Delay after raising the pen",
    "pen_delay_down": "Delay after lowering the pen",
    "reordering": "Path order",
    "hiding": "Hidden-line removal",
    "resolution": "Resolution",
}
ADVANCED_RANGES = {
    "pen_up": (0, 100),
    "speed_pendown": (1, 100),
    "speed_penup": (1, 100),
    "accel": (1, 100),
    "pen_rate_raise": (1, 100),
    "pen_rate_lower": (1, 100),
    "pen_delay_up": (0, 1000),
    "pen_delay_down": (0, 1000),
}
ADVANCED_CHOICES = {"reordering": (0, 1, 2, 4), "resolution": (1, 2)}
_AUTOMATIC = ("pen_up", "speed_pendown")  # None means "Rosetta decides"


def advanced_from_dict(values: dict) -> Advanced:
    """Advanced options from the page or settings.json. ValueError with a plain message if one is wrong."""
    for name, value in values.items():
        label = ADVANCED_LABELS.get(name)
        if label is None:
            raise ValueError(f"Unknown advanced option: {name}")
        if name == "hiding":
            if not isinstance(value, bool):
                raise ValueError(f"{label} must be on or off.")
            continue
        if value is None and name in _AUTOMATIC:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} must be a whole number.")
        if name in ADVANCED_CHOICES:
            choices = ADVANCED_CHOICES[name]
            if value not in choices:
                raise ValueError(f"{label} must be one of {', '.join(str(choice) for choice in choices)}.")
        else:
            low, high = ADVANCED_RANGES[name]
            if not low <= value <= high:
                raise ValueError(f"{label} must be from {low} to {high}.")
    return Advanced(**values)


@dataclass
class PlotSettings:
    model: int  # EMS model number (rosetta.models.MODELS)
    penlift: int = 1  # EMS penlift: 1 default for model, 2 standard servo, 3 brushless
    pen_down: int = 30  # pen-down height, percent
    pen_type: str = "fineliner"  # key into rosetta.models.PEN_TYPES
    advanced: Advanced = field(default_factory=Advanced)

    @property
    def pen_up(self) -> int:
        if self.advanced.pen_up is not None:
            return self.advanced.pen_up
        return min(100, max(60, self.pen_down + 20))


def apply_settings(ad, settings: PlotSettings) -> None:
    """Set EMS options. Call after ad.plot_setup() or ad.interactive()."""
    if settings.model not in MODELS:
        raise ValueError(f"Unknown AxiDraw model number: {settings.model}")
    if settings.pen_type not in PEN_TYPES:
        raise ValueError(f"Unknown pen type: {settings.pen_type}")
    if settings.penlift not in (1, 2, 3):
        raise ValueError(f"Unknown pen lift: {settings.penlift!r} (use 1, 2 or 3)")
    pen_down = settings.pen_down
    whole_number = isinstance(pen_down, int) and not isinstance(pen_down, bool)
    if not whole_number or not 0 <= pen_down <= PEN_DOWN_MAX:
        raise ValueError(f"Pen-down height must be a whole number, 0 to {PEN_DOWN_MAX}: {pen_down!r}")
    advanced = advanced_from_dict(dataclasses.asdict(settings.advanced))
    if advanced.pen_up is not None and advanced.pen_up - pen_down < MIN_PEN_TRAVEL:
        raise ValueError(f"Pen-up height must be at least {MIN_PEN_TRAVEL} above the pen-down height.")
    options = ad.options
    options.model = settings.model
    options.penlift = settings.penlift
    options.pen_pos_down = pen_down
    options.pen_pos_up = settings.pen_up
    options.speed_pendown = advanced.speed_pendown or PEN_TYPES[settings.pen_type].speed_pendown
    options.speed_penup = advanced.speed_penup
    options.accel = advanced.accel
    options.pen_rate_raise = advanced.pen_rate_raise
    options.pen_rate_lower = advanced.pen_rate_lower
    options.pen_delay_up = advanced.pen_delay_up
    options.pen_delay_down = advanced.pen_delay_down
    options.auto_rotate = False  # spec §4: never rotate; screen = paper
    options.reordering = advanced.reordering
    options.hiding = advanced.hiding
    options.resolution = advanced.resolution


def ensure_std_streams() -> None:
    """Windowed (no-console) builds have sys.stdout/sys.stderr = None, and EMS writes to them."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def _log_ems_message(text) -> None:
    """EMS reports pauses, warnings and the like through a callback; Rosetta keeps them in the log."""
    logging.getLogger("rosetta.ems").info(text)


def make_axidraw():
    """A fresh EMS AxiDraw object. Imported lazily so non-engine code loads fast."""
    ensure_std_streams()
    from pyaxidraw import axidraw

    return axidraw.AxiDraw(user_message_fun=_log_ems_message)
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_engine_options.py -v`
Expected: all pass.
Run: `.venv\Scripts\python -m pytest -q`
Expected: all pass. Some test might still build `PlotSettings(reordering=...)` or `PlotSettings(hiding=...)`. If so, change it to `PlotSettings(..., advanced=Advanced(reordering=...))`.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\engine\options.py tests\test_engine_options.py
git commit -m "feat: Advanced engine options, validated before the engine sees them" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `UserProblem` and paper sizes

**Files:**
- Modify: `src/rosetta/errors.py`
- Create: `src/rosetta/app/paper.py`
- Test: `tests/test_paper.py`

- [ ] **Step 1: Write the failing test**

`tests/test_paper.py`:
```python
import math

import pytest

from rosetta.app.paper import CUSTOM, PAPER_SIZES, paper_dimensions
from rosetta.errors import UserProblem


def test_the_spec_presets_are_all_there():
    assert list(PAPER_SIZES) == ["letter", "legal", "tabloid", "a4", "a3", "a2", "a1"]


def test_landscape_runs_the_long_side_along_the_rail():
    assert paper_dimensions("letter", "landscape") == pytest.approx((279.4, 215.9))


def test_portrait_runs_the_long_side_toward_the_student():
    assert paper_dimensions("a4", "portrait") == pytest.approx((210.0, 297.0))


def test_custom_sizes_are_taken_as_typed():
    assert paper_dimensions(CUSTOM, "portrait", 300, 200) == (300.0, 200.0)


@pytest.mark.parametrize("width, height", [
    (0, 100), (-5, 100), (math.nan, 100), (100, math.inf), (5000, 100), (None, 100), (True, 100), ("10", 100),
])
def test_custom_sizes_must_be_usable(width, height):
    with pytest.raises(UserProblem, match="between 0 and 2000 mm"):
        paper_dimensions(CUSTOM, "landscape", width, height)


def test_unknown_size_or_orientation_is_a_programming_error():
    with pytest.raises(ValueError):
        paper_dimensions("b5", "landscape")
    with pytest.raises(ValueError):
        paper_dimensions("a4", "sideways")


def test_user_problem_keeps_its_details():
    problem = UserProblem("The plot stopped.", details="SerialException: gone")
    assert (str(problem), problem.details) == ("The plot stopped.", "SerialException: gone")
    assert UserProblem("Plain.").details == ""
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python -m pytest tests\test_paper.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'rosetta.app.paper'`.

- [ ] **Step 3: Write the code**

Append to `src/rosetta/errors.py`:
```python


class UserProblem(Exception):
    """Something the student asked for can't be done. str(exc) is a plain-language message for the
    student; `details` is technical text for the app's Details link (often empty)."""

    def __init__(self, message: str, details: str = ""):
        super().__init__(message)
        self.details = details
```

`src/rosetta/app/paper.py`:
```python
"""Paper sizes the student picks from in the Material step (spec §5, step 2).

Width runs along the rail (left-right on screen), height toward the student. Every AxiDraw reaches
farther along its rail than toward the student, so landscape is the default.
"""
import math
from dataclasses import dataclass

from rosetta.errors import UserProblem
from rosetta.units import MM_PER_INCH

ORIENTATIONS = ("landscape", "portrait")
DEFAULT_ORIENTATION = "landscape"
CUSTOM = "custom"
MAX_CUSTOM_MM = 2000.0  # bigger than any AxiDraw's reach; anything larger is a typo


@dataclass(frozen=True)
class PaperSize:
    key: str
    label: str
    short_mm: float
    long_mm: float


PAPER_SIZES = {
    paper.key: paper
    for paper in (
        PaperSize("letter", "Letter", 8.5 * MM_PER_INCH, 11 * MM_PER_INCH),
        PaperSize("legal", "Legal", 8.5 * MM_PER_INCH, 14 * MM_PER_INCH),
        PaperSize("tabloid", "Tabloid 11×17", 11 * MM_PER_INCH, 17 * MM_PER_INCH),
        PaperSize("a4", "A4", 210.0, 297.0),
        PaperSize("a3", "A3", 297.0, 420.0),
        PaperSize("a2", "A2", 420.0, 594.0),
        PaperSize("a1", "A1", 594.0, 841.0),
    )
}


def paper_dimensions(
    size: str, orientation: str, custom_width_mm=None, custom_height_mm=None
) -> tuple[float, float]:
    """(width, height) in mm on the machine. Custom sizes are taken exactly as typed (the page swaps
    its two fields when the student flips the orientation)."""
    if orientation not in ORIENTATIONS:
        raise ValueError(f"Unknown orientation: {orientation!r}")
    if size == CUSTOM:
        for value in (custom_width_mm, custom_height_mm):
            if not _usable_length(value):
                raise UserProblem(f"Paper width and height must be between 0 and {MAX_CUSTOM_MM:g} mm.")
        return float(custom_width_mm), float(custom_height_mm)
    paper = PAPER_SIZES.get(size)
    if paper is None:
        raise ValueError(f"Unknown paper size: {size!r}")
    if orientation == "landscape":
        return paper.long_mm, paper.short_mm
    return paper.short_mm, paper.long_mm


def _usable_length(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 < value <= MAX_CUSTOM_MM
    )
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_paper.py -v`
Expected: `14 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\errors.py src\rosetta\app\paper.py tests\test_paper.py
git commit -m "feat: paper presets and UserProblem for student-facing errors" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Settings that never fail to load

Spec §6.4: `%APPDATA%\RosettaPlotter\settings.json` holds the units, the last paper, the advanced options, and pen settings per plotter, keyed by the plotter's nickname.
- It also holds §8's laptop-side model memory for plotters whose firmware is too old to store it, keyed by serial port.
- A damaged file must never stop a student from plotting. So a bad file is set aside, and a bad value falls back to its default.
- **Deviation from the spec:** §6.4 lists "pen-type speed presets". Those stay in `rosetta.models.PEN_TYPES`, tuned in code after hardware testing. A laptop that needs a different speed uses the Advanced pen-down speed instead. That keeps one place to change them.

**Files:**
- Create: `src/rosetta/app/settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write the failing test**

`tests/test_settings.py`:
```python
import json
import os

from rosetta.app.settings import (
    PaperChoice, PenProfile, Settings, SettingsStore, StoredIdentity, app_folder,
)
from rosetta.engine.options import Advanced


def _store_with(tmp_path, data) -> SettingsStore:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return SettingsStore(path)


def test_a_missing_file_gives_the_defaults(tmp_path):
    assert SettingsStore(tmp_path / "settings.json").settings == Settings()


def test_settings_survive_a_save_and_load(tmp_path):
    store = SettingsStore(tmp_path / "RosettaPlotter" / "settings.json")
    store.settings.units = "mm"
    store.settings.paper = PaperChoice("custom", "portrait", 300.0, 200.0)
    store.settings.margin_mm = 10.0
    store.settings.advanced = Advanced(accel=60, hiding=True)
    store.settings.profiles["PSU Lab m5p1"] = PenProfile(45, "marker")
    store.settings.old_firmware["COM7"] = StoredIdentity(3, 1, "Old one")
    store.save()
    assert SettingsStore(store.path).settings == store.settings


def test_a_damaged_file_is_set_aside(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")
    assert SettingsStore(path).settings == Settings()
    assert (tmp_path / "settings.json.bad").read_text(encoding="utf-8") == "{ not json"


def test_a_file_that_is_not_an_object_is_set_aside(tmp_path):
    assert _store_with(tmp_path, [1, 2]).settings == Settings()
    assert (tmp_path / "settings.json.bad").exists()


def test_one_bad_value_falls_back_to_its_default(tmp_path):
    settings = _store_with(tmp_path, {"units": "furlongs", "margin_mm": 12}).settings
    assert (settings.units, settings.margin_mm) == ("in", 12.0)


def test_bad_advanced_options_are_dropped_one_by_one(tmp_path):
    settings = _store_with(tmp_path, {"advanced": {"accel": 500, "speed_penup": 50, "warp": 1}}).settings
    assert settings.advanced == Advanced(speed_penup=50)


def test_a_custom_paper_without_its_size_falls_back(tmp_path):
    settings = _store_with(tmp_path, {"paper": {"size": "custom", "orientation": "portrait"}}).settings
    assert settings.paper == PaperChoice("letter", "portrait", None, None)


def test_profiles_keep_what_is_usable(tmp_path):
    settings = _store_with(tmp_path, {"profiles": {
        "PSU Lab m5p1": {"pen_down": 45, "pen_type": "marker"},
        "Other m1p1": {"pen_down": 99, "pen_type": "crayon"},
        "Broken": "not a profile",
    }}).settings
    assert settings.profiles == {"PSU Lab m5p1": PenProfile(45, "marker"), "Other m1p1": PenProfile()}


def test_old_firmware_identities_need_a_real_model(tmp_path):
    settings = _store_with(tmp_path, {"old_firmware": {
        "COM3": {"model": 5, "penlift": 3, "label": "Lab"},
        "COM4": {"model": 99},
        "COM5": {"model": 2, "penlift": "high"},
    }}).settings
    assert settings.old_firmware == {"COM3": StoredIdentity(5, 3, "Lab")}


def test_a_failed_save_is_logged_not_raised(tmp_path, monkeypatch, caplog):
    store = SettingsStore(tmp_path / "settings.json")

    def refuse(*args):
        raise PermissionError("locked")

    monkeypatch.setattr(os, "replace", refuse)
    store.save()
    assert "Couldn't save settings" in caplog.text


def test_app_folder_is_under_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert app_folder() == tmp_path / "RosettaPlotter"
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python -m pytest tests\test_settings.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'rosetta.app.settings'`.

- [ ] **Step 3: Write `src/rosetta/app/settings.py`**

```python
"""Per-laptop settings in %APPDATA%\\RosettaPlotter\\settings.json (spec §6.4).

Loading never fails: a missing file gives the defaults, a damaged one is set aside as
settings.json.bad, and a single bad value falls back to its own default.
"""
import dataclasses
import json
import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from rosetta.app.paper import CUSTOM, DEFAULT_ORIENTATION, MAX_CUSTOM_MM, ORIENTATIONS, PAPER_SIZES
from rosetta.compose import DEFAULT_MARGIN_MM
from rosetta.engine.options import PEN_DOWN_MAX, Advanced, advanced_from_dict
from rosetta.models import MODELS, PEN_TYPES

logger = logging.getLogger(__name__)

APP_FOLDER = "RosettaPlotter"
SETTINGS_VERSION = 1
UNITS = ("in", "mm")
MAX_MARGIN_MM = 50.0


def app_folder() -> Path:
    """%APPDATA%\\RosettaPlotter (under the home folder if APPDATA isn't set)."""
    return Path(os.environ.get("APPDATA") or Path.home()) / APP_FOLDER


@dataclass
class PaperChoice:
    size: str = "letter"
    orientation: str = DEFAULT_ORIENTATION
    custom_width_mm: float | None = None
    custom_height_mm: float | None = None


@dataclass
class PenProfile:
    """What a plotter was last used with, so the next session on it starts there."""

    pen_down: int = 30
    pen_type: str = "fineliner"


@dataclass
class StoredIdentity:
    """A plotter whose firmware is too old to hold its model, remembered on this laptop (spec §8)."""

    model: int
    penlift: int = 1
    label: str = ""


@dataclass
class Settings:
    units: str = "in"
    paper: PaperChoice = field(default_factory=PaperChoice)
    margin_mm: float = DEFAULT_MARGIN_MM
    advanced: Advanced = field(default_factory=Advanced)
    profiles: dict[str, PenProfile] = field(default_factory=dict)  # keyed by Machine.profile_key()
    old_firmware: dict[str, StoredIdentity] = field(default_factory=dict)  # keyed by serial port


class SettingsStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.settings = self._load()

    def save(self) -> None:
        """Write atomically. A failure is logged, not raised: losing a preference mustn't stop a plot."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            scratch = self.path.with_name(self.path.name + ".tmp")
            scratch.write_text(json.dumps(_to_json(self.settings), indent=2), encoding="utf-8")
            os.replace(scratch, self.path)
        except OSError:
            logger.warning("Couldn't save settings to %s", self.path, exc_info=True)

    def _load(self) -> Settings:
        try:
            text = self.path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return Settings()
        except OSError:
            logger.warning("Couldn't read %s; using the default settings", self.path, exc_info=True)
            return Settings()
        except UnicodeDecodeError:
            self._set_aside()
            return Settings()
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            self._set_aside()
            return Settings()
        return _from_json(data)

    def _set_aside(self) -> None:
        logger.warning("%s is damaged; keeping it as settings.json.bad and using the defaults", self.path)
        try:
            os.replace(self.path, self.path.with_name(self.path.name + ".bad"))
        except OSError:
            logger.warning("Couldn't set %s aside", self.path, exc_info=True)


def _to_json(settings: Settings) -> dict:
    return {"version": SETTINGS_VERSION, **dataclasses.asdict(settings)}


def _from_json(data: dict) -> Settings:
    defaults = Settings()
    return Settings(
        units=_choice(data.get("units"), UNITS, defaults.units),
        paper=_paper(data.get("paper")),
        margin_mm=_number(data.get("margin_mm"), 0.0, MAX_MARGIN_MM, defaults.margin_mm),
        advanced=_advanced(data.get("advanced")),
        profiles=_profiles(data.get("profiles")),
        old_firmware=_identities(data.get("old_firmware")),
    )


def _choice(value, choices, default):
    return value if isinstance(value, str) and value in choices else default


def _number(value, low, high, default):
    usable = (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and low <= value <= high
    )
    return float(value) if usable else default


def _whole(value, low, high, default):
    usable = isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    return value if usable else default


def _paper(data) -> PaperChoice:
    default = PaperChoice()
    if not isinstance(data, dict):
        return default
    size = _choice(data.get("size"), (*PAPER_SIZES, CUSTOM), default.size)
    width = _number(data.get("custom_width_mm"), 0.1, MAX_CUSTOM_MM, None)
    height = _number(data.get("custom_height_mm"), 0.1, MAX_CUSTOM_MM, None)
    if size == CUSTOM and (width is None or height is None):
        size = default.size
    orientation = _choice(data.get("orientation"), ORIENTATIONS, default.orientation)
    return PaperChoice(size, orientation, width, height)


def _advanced(data) -> Advanced:
    if not isinstance(data, dict):
        return Advanced()
    kept = {}
    for name, value in data.items():
        try:
            advanced_from_dict({name: value})
        except (ValueError, TypeError):
            logger.warning("Ignoring the saved advanced option %s=%r", name, value)
            continue
        kept[name] = value
    return Advanced(**kept)


def _profiles(data) -> dict[str, PenProfile]:
    if not isinstance(data, dict):
        return {}
    default = PenProfile()
    return {
        key: PenProfile(
            _whole(value.get("pen_down"), 0, PEN_DOWN_MAX, default.pen_down),
            _choice(value.get("pen_type"), tuple(PEN_TYPES), default.pen_type),
        )
        for key, value in data.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def _identities(data) -> dict[str, StoredIdentity]:
    if not isinstance(data, dict):
        return {}
    kept = {}
    for port, value in data.items():
        if not (isinstance(port, str) and isinstance(value, dict)):
            continue
        model = _whole(value.get("model"), 1, max(MODELS), None)
        penlift = _whole(value.get("penlift", 1), 1, 3, None)
        label = value.get("label", "")
        if model in MODELS and penlift is not None and isinstance(label, str):
            kept[port] = StoredIdentity(model, penlift, label)
    return kept
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_settings.py -v`
Expected: `11 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\app\settings.py tests\test_settings.py
git commit -m "feat: per-laptop settings that never fail to load" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The app's log file and Copy diagnostics

Spec §10: logs rotate under `%APPDATA%\RosettaPlotter\logs\`, and **Copy diagnostics** puts the recent log plus system info on the clipboard. `plan2-notes.md` adds that `rosetta.ems` (EMS's own messages) must land in the app log at INFO.

**Files:**
- Create: `src/rosetta/app/logs.py`
- Test: `tests/test_logs.py`

- [ ] **Step 1: Write the failing test**

`tests/test_logs.py`:
```python
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
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python -m pytest tests\test_logs.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'rosetta.app.logs'`.

- [ ] **Step 3: Write `src/rosetta/app/logs.py`**

```python
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
    setattr(handler, _OWNED, True)
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(_QuietLibraries())
    logging.getLogger("rosetta").setLevel(logging.INFO)
    for name in _LOGGERS:
        logging.getLogger(name).addHandler(handler)
    return Path(handler.baseFilename)


def stop_logging() -> None:
    """Remove and close the handler setup_logging added (flushing the file)."""
    closed = set()
    for name in _LOGGERS:
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            if getattr(handler, _OWNED, False):
                logger.removeHandler(handler)
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
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_logs.py -v`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\app\logs.py tests\test_logs.py
git commit -m "feat: rotating app log and Copy diagnostics text" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Keep the normalized drawing for the canvas (`Artwork.preview_svg`)

Spec §6.5: "the browser's SVG rendering of the original file shown under the cached geometry."
- The normalized document is the one to keep. It always has a mm size and a `viewBox`, so the browser scales it exactly like the polylines.
- Its `<style>` rules are still there, so fills and stroke widths look like the student's file.
- The page will show it through an SVG `<image href="data:image/svg+xml;base64,...">`. Browsers never run scripts or fetch anything from an SVG used as an image, so student files stay inert.

**Files:**
- Modify: `src/rosetta/loader.py`
- Test: `tests/test_loader.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_loader.py`:
```python
from lxml import etree


def test_artwork_keeps_its_normalized_drawing_for_the_canvas(tmp_path):
    path = tmp_path / "logo.svg"
    path.write_bytes(samples.ILLUSTRATOR_EXPORT)
    root = etree.fromstring(load_artwork(path).preview_svg.encode("utf-8"))
    assert float(root.get("width").removesuffix("mm")) == pytest.approx(200, abs=0.001)
    assert root.get("viewBox") is not None


def test_pdf_artwork_has_a_preview_too(tmp_path):
    art = load_artwork(_two_page_pdf(tmp_path / "two.pdf"), page=1)
    assert art.preview_svg.startswith("<svg") and "<path" in art.preview_svg
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `.venv\Scripts\python -m pytest tests\test_loader.py -v -k preview`
Expected: 2 failures, `AttributeError: 'Artwork' object has no attribute 'preview_svg'`.

- [ ] **Step 3: Change `src/rosetta/loader.py`**

Add `from lxml import etree` to the imports. Give `Artwork` a last field with a default, so existing constructors keep working:
```python
@dataclass
class Artwork:
    name: str
    width_mm: float  # the document/artboard size, used as the piece's frame
    height_mm: float
    shapes: list[Shape]
    issues: list[Issue]
    source: str
    # The normalized drawing as SVG text (mm size, viewBox, CSS inlined), for the app to show under the
    # lines it will plot. Shown as an <image>, so a student file's scripts never run.
    preview_svg: str = ""
```
In `load_artwork`, take the snapshot before flattening, and pass it into the result:
```python
    if extension == ".svg":
        doc, name, extra_issues = _read_svg(path)
    else:
        doc, name, extra_issues = _read_pdf(path, page)
    preview_svg = etree.tostring(doc.root, encoding="unicode")

    report = flatten_with_report(doc)
```
and change the last line to:
```python
    return Artwork(name, doc.width_mm, doc.height_mm, shapes, issues, doc.source, preview_svg)
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_loader.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\loader.py tests\test_loader.py
git commit -m "feat: keep the normalized drawing on Artwork for the canvas" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The pen's planned path (`engine/preview.py`)

Spec §5, step 5: the preview "animates the planned path: pen-down moves in color, pen-up moves faint. It can be scrubbed."
- The path must be the one EMS will really take, after its reordering. EMS's own preview layer can't give that, because it splits pen-up and pen-down into two unordered path strings.
- In preview mode EMS calls `ad.preview.log_sm_move(ad, move)` once for every planned move, in order. At that moment `ad.pen.phys.xpos/ypos` (inches) is where the move starts and `ad.pen.phys.z_up` tells the pen state. `move[2][0:2]` is where it ends, and `move[1][2]` is its duration in ms.
- So `plan_layer()` swaps that method for a recorder, using the same `dry_run` that `estimate()` uses.
- **Timing:** the recorded clock leaves out pen lifts (about 4% short on a small plot). So the recorded times are scaled to end exactly at EMS's estimate.

**Files:**
- Modify: `src/rosetta/engine/runner.py` (split `estimate`)
- Create: `src/rosetta/engine/preview.py`
- Test: `tests/test_preview.py`, `tests/test_engine_contract.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_engine_contract.py`:
```python
def test_preview_logger_used_for_the_planned_path():
    ad = axidraw.AxiDraw()
    assert list(inspect.signature(ad.preview.log_sm_move).parameters) == ["ad_ref", "move"]
    assert hasattr(ad.pen.phys, "z_up")
```

`tests/test_preview.py`:
```python
import math
from itertools import pairwise

import pytest

from rosetta.compose import ColorGroup
from rosetta.engine.options import PlotSettings
from rosetta.engine.preview import plan_layer
from rosetta.engine.runner import estimate
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg

SETTINGS = PlotSettings(model=1)
SQUARE = [(10.0, 10.0), (110.0, 10.0), (110.0, 110.0), (10.0, 110.0), (10.0, 10.0)]
LINE = [(20.0, 150.0), (120.0, 150.0)]


def _plot(*lines) -> str:
    return plot_svg(get_model(1), [ColorGroup("#000000", list(lines))])


def _length(points) -> float:
    return sum(math.dist(a[:2], b[:2]) for a, b in pairwise(points))


def test_the_plan_agrees_with_the_estimate():
    svg = _plot(SQUARE, LINE)
    plan, expected = plan_layer(svg, 1, SETTINGS), estimate(svg, 1, SETTINGS)
    assert plan.seconds == pytest.approx(expected.seconds)
    assert plan.pendown_m == pytest.approx(expected.pendown_m)


def test_the_plan_draws_every_line_once():
    plan = plan_layer(_plot(SQUARE, LINE), 1, SETTINGS)
    assert sum(_length(run.points) for run in plan.runs if run.down) == pytest.approx(500.0, abs=0.5)


def test_the_plan_starts_and_ends_at_home():
    runs = plan_layer(_plot(SQUARE), 1, SETTINGS).runs
    assert not runs[0].down and runs[0].points[0][:2] == pytest.approx((0, 0), abs=0.01)
    assert not runs[-1].down and runs[-1].points[-1][:2] == pytest.approx((0, 0), abs=0.01)


def test_times_rise_to_the_estimate():
    plan = plan_layer(_plot(SQUARE, LINE), 1, SETTINGS)
    times = [t for run in plan.runs for _x, _y, t in run.points]
    assert times == sorted(times)
    assert times[-1] == pytest.approx(plan.seconds)


def test_pen_up_and_pen_down_runs_take_turns():
    runs = plan_layer(_plot(SQUARE, LINE), 1, SETTINGS).runs
    assert all(a.down != b.down for a, b in pairwise(runs))


def test_straight_moves_keep_only_their_corners():
    drawing = [run for run in plan_layer(_plot(SQUARE), 1, SETTINGS).runs if run.down]
    assert len(drawing) == 1 and len(drawing[0].points) == 5


def test_an_unreadable_plot_is_a_value_error():
    with pytest.raises(ValueError):
        plan_layer("<svg", 1, SETTINGS)
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `.venv\Scripts\python -m pytest tests\test_preview.py tests\test_engine_contract.py -v`
Expected: collection error for `test_preview.py`, `ModuleNotFoundError: No module named 'rosetta.engine.preview'`. The contract test passes already, since it only pins what EMS has.

- [ ] **Step 3: Split `estimate()` in `src/rosetta/engine/runner.py`**

Replace the whole `estimate` function with these three functions:
```python
def estimate(svg_text: str, layer: int, settings: PlotSettings, factory=make_axidraw) -> Estimate:
    """Time and pen-down distance for one layer. Raises ValueError if the plot can't be read."""
    return dry_run_estimate(dry_run(svg_text, layer, settings, factory))


def dry_run(svg_text: str, layer: int, settings: PlotSettings, factory=make_axidraw, on_move=None):
    """Run one layer through EMS in preview mode (no plotter) and return the engine object.

    on_move(ad, move), if given, sees every planned move in order: it replaces EMS's preview logger,
    ad.preview.log_sm_move, which does nothing while rendering is off. Raises ValueError if the plot
    can't be read.
    """
    settings = dataclasses.replace(settings)
    try:
        ad = factory()
        ad.plot_setup(_clean(svg_text))
    except Exception as exc:
        logger.exception("Couldn't set up the plot to estimate it")
        raise ValueError(_UNREADABLE) from exc
    apply_settings(ad, settings)
    ad.options.mode = "layers"
    ad.options.layer = layer
    ad.options.preview = True
    ad.options.rendering = 0
    if on_move is not None:
        ad.preview.log_sm_move = on_move
    try:
        ad.plot_run()
    except Exception as exc:
        logger.exception("Couldn't estimate the plot")
        raise ValueError(_UNREADABLE) from exc
    if ad.digest is None:  # EMS gave up quietly, e.g. a page without a size in mm or inches
        raise ValueError(_UNREADABLE)
    return ad


def dry_run_estimate(ad) -> Estimate:
    """Time and pen-down distance from an engine object that dry_run() has run."""
    stats = ad.plot_status.stats
    # EMS fills down_travel_tot in its report; down_travel_inch is the fallback.
    pendown_in = max(stats.down_travel_tot, stats.down_travel_inch)
    return Estimate(stats.pt_estimate / 1000.0, pendown_in * MM_PER_INCH / 1000.0)
```

- [ ] **Step 4: Write `src/rosetta/engine/preview.py`**

```python
"""The path the pen will take, in order and with times, for the Plot step's animated preview (spec §5).

EMS calls ad.preview.log_sm_move(ad, move) for every planned move of a preview run. dry_run() lets
a recorder stand in for it, so the path is exactly the one EMS will plot, after its own reordering.
"""
import math
from dataclasses import dataclass

from rosetta.engine.options import PlotSettings, make_axidraw
from rosetta.engine.runner import dry_run, dry_run_estimate
from rosetta.units import MM_PER_INCH

COLLINEAR_MM = 1e-3  # a middle point this close to the line through its neighbours adds nothing
SAME_POINT_MM = 1e-6

Point = tuple[float, float, float]  # x mm, y mm, seconds from the start of the layer


@dataclass(frozen=True)
class Run:
    """Consecutive moves with the pen down (drawing) or up (travelling)."""

    down: bool
    points: list[Point]


@dataclass(frozen=True)
class LayerPlan:
    seconds: float
    pendown_m: float
    runs: list[Run]


class _Recorder:
    def __init__(self):
        self.runs: list[Run] = []
        self.clock_ms = 0.0

    def __call__(self, ad, move) -> None:
        # move = ['SM', (steps2, steps1, duration_ms), (x_in, y_in, pen_up, distance_in, ...)]
        start = (ad.pen.phys.xpos * MM_PER_INCH, ad.pen.phys.ypos * MM_PER_INCH)
        end = (move[2][0] * MM_PER_INCH, move[2][1] * MM_PER_INCH)
        down = not ad.pen.phys.z_up
        started = self.clock_ms / 1000.0
        self.clock_ms += move[1][2]
        point = (end[0], end[1], self.clock_ms / 1000.0)
        last = self.runs[-1] if self.runs else None
        if last is not None and last.down == down and math.dist(last.points[-1][:2], start) <= SAME_POINT_MM:
            last.points.append(point)
        else:
            self.runs.append(Run(down, [(start[0], start[1], started), point]))


def plan_layer(svg_text: str, layer: int, settings: PlotSettings, factory=make_axidraw) -> LayerPlan:
    """Time, pen-down distance and the planned path of one layer. Raises ValueError if the plot
    can't be read. Times are scaled so the path ends at EMS's estimate (pen lifts take time too)."""
    recorder = _Recorder()
    ad = dry_run(svg_text, layer, settings, factory, on_move=recorder)
    result = dry_run_estimate(ad)
    recorded = recorder.clock_ms / 1000.0
    scale = result.seconds / recorded if recorded > 0 else 1.0
    runs = [
        Run(run.down, _simplified([(x, y, t * scale) for x, y, t in run.points]))
        for run in recorder.runs
    ]
    return LayerPlan(result.seconds, result.pendown_m, runs)


def _simplified(points: list[Point]) -> list[Point]:
    """Drop middle points that lie on the straight line between their neighbours.

    EMS splits every straight stroke into many short moves (speeding up, cruising, slowing down);
    the page only needs the corners.
    """
    kept = [points[0]]
    for index in range(1, len(points) - 1):
        (ax, ay, _), (bx, by, _), (cx, cy, _) = kept[-1], points[index], points[index + 1]
        length = math.hypot(cx - ax, cy - ay)
        if length > 0:
            offset = abs((cx - ax) * (ay - by) - (ax - bx) * (cy - ay)) / length
            along = ((bx - ax) * (cx - ax) + (by - ay) * (cy - ay)) / length
            if offset <= COLLINEAR_MM and 0 <= along <= length:
                continue
        kept.append(points[index])
    kept.append(points[-1])
    return kept
```

- [ ] **Step 5: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_preview.py tests\test_runner.py tests\test_engine_contract.py -v`
Expected: all pass.
Run: `.venv\Scripts\python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add src\rosetta\engine\runner.py src\rosetta\engine\preview.py tests\test_preview.py tests\test_engine_contract.py
git commit -m "feat: record the engine's planned pen path for the Plot preview" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The session and its JSON for the page

**Files:**
- Create: `src/rosetta/app/session.py`, `src/rosetta/app/payloads.py`
- Test: `tests/test_session.py`

`Session` holds the paper and the pieces. The plotter's model and pen live on `Machine` (Task 9), and the plot lives in `PlotController` (Task 12). `payloads.py` turns these objects into the plain JSON the page receives:
- coordinates are rounded to 0.01 mm, finer than the plotter can draw, to keep big files small;
- lines are grouped by pen color.

- [ ] **Step 1: Write the failing test**

`tests/test_session.py`:
```python
import base64

import pymupdf
import pytest

from rosetta.app.payloads import job_payload, material_payload, piece_payload
from rosetta.app.session import DUPLICATE_OFFSET_MM, GONE, Session, pages_in
from rosetta.compose import Material
from rosetta.errors import ImportProblem, UserProblem
from rosetta.models import get_model

LETTER = Material(0.0, 0.0, 279.4, 215.9)
TWO_COLORS = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 100 50">
<path d="M10 10 H90" stroke="#000000" fill="none"/>
<path d="M10 30 H90.004" stroke="#ff0000" fill="none"/>
<rect x="0" y="0" width="100" height="50" fill="#ffffff"/>
</svg>"""


def _svg(tmp_path, text=TWO_COLORS, name="art.svg"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_an_import_lands_centered_on_the_paper(tmp_path):
    session = Session(LETTER)
    piece, shrunk = session.add(_svg(tmp_path))
    assert piece.id == "piece-1" and not shrunk
    assert (piece.placement.x, piece.placement.y) == pytest.approx(((279.4 - 100) / 2, (215.9 - 50) / 2))


def test_artwork_bigger_than_the_paper_is_shrunk_and_says_so(tmp_path):
    big = TWO_COLORS.replace('width="100mm" height="50mm"', 'width="1000mm" height="500mm"')
    piece, shrunk = Session(LETTER).add(_svg(tmp_path, big))
    assert shrunk and piece.placement.scale < 0.3


def test_place_duplicate_and_remove(tmp_path):
    session = Session(LETTER)
    first, _ = session.add(_svg(tmp_path))
    session.place(first.id, 5, 6, 0.5, 450)
    assert (first.placement.x, first.placement.y, first.placement.scale, first.placement.rotation) == (5, 6, 0.5, 90)
    copy = session.duplicate(first.id)
    assert copy.id == "piece-2" and copy.artwork is first.artwork
    assert (copy.placement.x, copy.placement.y) == (5 + DUPLICATE_OFFSET_MM, 6 + DUPLICATE_OFFSET_MM)
    session.remove(first.id)
    assert [piece.id for piece in session.pieces] == ["piece-2"]
    with pytest.raises(UserProblem, match=GONE):
        session.get(first.id)


@pytest.mark.parametrize("x, y, scale, rotation", [
    (float("nan"), 0, 1, 0), (0, float("inf"), 1, 0), (0, 0, 0, 0), (0, 0, -1, 0), (0, 0, 1, 45),
])
def test_bad_placements_are_refused(tmp_path, x, y, scale, rotation):
    session = Session(LETTER)
    piece, _ = session.add(_svg(tmp_path))
    with pytest.raises(ValueError):
        session.place(piece.id, x, y, scale, rotation)


def test_compose_skips_white_unless_asked(tmp_path):
    session = Session(LETTER)
    session.add(_svg(tmp_path))
    assert [group.name for group in session.compose(get_model(1)).groups] == ["black", "red"]
    session.skip_white = False
    assert [group.name for group in session.compose(get_model(1)).groups] == ["black", "red", "white"]


def test_page_counts(tmp_path):
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page()
    doc.save(tmp_path / "three.pdf")
    doc.close()
    assert pages_in(tmp_path / "three.pdf") == 3
    assert pages_in(_svg(tmp_path)) == 1
    with pytest.raises(ImportProblem, match="can't be found"):
        pages_in(tmp_path / "missing.pdf")


def test_piece_payload_groups_lines_by_color(tmp_path):
    piece, _ = Session(LETTER).add(_svg(tmp_path))
    payload = piece_payload(piece)
    assert payload["id"] == "piece-1" and payload["name"] == "art"
    assert (payload["width_mm"], payload["height_mm"]) == pytest.approx((100, 50))
    groups = {group["color"]: group for group in payload["groups"]}
    assert groups["#000000"]["lines"] == [[10.0, 10.0, 90.0, 10.0]]
    assert groups["#ff0000"]["lines"] == [[10.0, 30.0, 90.0, 30.0]]  # rounded to 0.01 mm
    assert groups["#ffffff"]["white"] and not groups["#000000"]["white"]
    assert {issue["code"] for issue in payload["issues"]} == {"white"}
    preview = payload["preview"].removeprefix("data:image/svg+xml;base64,")
    assert base64.b64decode(preview).decode("utf-8").startswith("<svg")


def test_material_payload_says_whether_the_paper_fits():
    assert material_payload(LETTER, get_model(1))["fits"] is True  # 279.4 x 215.9 on a 300 x 218 plotter
    a3 = material_payload(Material(0, 0, 420, 297), get_model(1))
    assert a3["fits"] is False and a3["reach"] == pytest.approx([299.97, 217.93], abs=0.01)
    assert material_payload(LETTER, None)["reach"] is None


def test_job_payload_lists_the_pens(tmp_path):
    session = Session(LETTER)
    session.add(_svg(tmp_path))
    payload = job_payload(session.compose(get_model(1)))
    assert [(c["layer"], c["name"], c["lines"]) for c in payload["colors"]] == [(1, "black", 1), (2, "red", 1)]
    assert not payload["empty"] and not payload["clipped"]
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python -m pytest tests\test_session.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'rosetta.app.payloads'`.

- [ ] **Step 3: Write `src/rosetta/app/session.py`**

```python
"""What the student is putting together (spec §6.4): the paper, and the pieces of artwork on it.

The plotter's model and pen settings live on Machine; the plot itself in PlotController.
Methods here are called from several bridge threads; each change is one list or attribute update.
"""
import dataclasses
import itertools
import math
from dataclasses import dataclass
from pathlib import Path

from rosetta.compose import (
    DEFAULT_MARGIN_MM, Job, Material, PlacedPiece, Placement, compose_job, initial_placement,
)
from rosetta.errors import ImportProblem, UserProblem
from rosetta.loader import Artwork, load_artwork
from rosetta.models import MachineModel
from rosetta.pdf_import import page_count

DUPLICATE_OFFSET_MM = 10.0
SHRUNK_BELOW = 0.99  # an import placed smaller than this was shrunk to fit, and the page says so
MAX_SCALE = 100.0
ROTATIONS = (0, 90, 180, 270)
GONE = "That drawing isn't on the paper anymore."


@dataclass
class Piece:
    id: str
    path: str
    page: int  # 0-based
    artwork: Artwork
    placement: Placement


def pages_in(path) -> int:
    """How many pages a file has: PDF and AI files can have several; everything else has one."""
    path = Path(path)
    if not path.is_file():
        raise ImportProblem(f"The file {path.name} can't be found.")
    if path.suffix.lower() in (".pdf", ".ai"):
        return page_count(path)
    return 1


class Session:
    def __init__(self, material: Material, margin_mm: float = DEFAULT_MARGIN_MM):
        self.material = material
        self.margin_mm = margin_mm
        self.skip_white = True
        self.pieces: list[Piece] = []
        self._ids = itertools.count(1)

    def add(self, path, page: int = 0) -> tuple[Piece, bool]:
        """Import a file onto the paper (slow for big files). Returns the piece and whether it was
        shrunk to fit inside the margins (spec §5, step 3)."""
        artwork = load_artwork(Path(path), page)
        placement = initial_placement(artwork, self.material, self.margin_mm)
        piece = Piece(self._new_id(), str(path), page, artwork, placement)
        self.pieces.append(piece)
        return piece, placement.scale < SHRUNK_BELOW

    def get(self, piece_id: str) -> Piece:
        for piece in self.pieces:
            if piece.id == piece_id:
                return piece
        raise UserProblem(GONE)

    def place(self, piece_id: str, x, y, scale, rotation) -> Piece:
        piece = self.get(piece_id)
        piece.placement = _checked(Placement(float(x), float(y), float(scale), int(rotation) % 360))
        return piece

    def duplicate(self, piece_id: str) -> Piece:
        original = self.get(piece_id)
        placement = dataclasses.replace(
            original.placement,
            x=original.placement.x + DUPLICATE_OFFSET_MM,
            y=original.placement.y + DUPLICATE_OFFSET_MM,
        )
        copy = Piece(self._new_id(), original.path, original.page, original.artwork, placement)
        self.pieces.insert(self.pieces.index(original) + 1, copy)
        return copy

    def remove(self, piece_id: str) -> None:
        self.pieces.remove(self.get(piece_id))

    def clear(self) -> None:
        self.pieces.clear()

    def compose(self, model: MachineModel) -> Job:
        placed = [PlacedPiece(piece.artwork, piece.placement) for piece in list(self.pieces)]
        return compose_job(model, self.material, placed, skip_white=self.skip_white)

    def _new_id(self) -> str:
        return f"piece-{next(self._ids)}"


def _checked(placement: Placement) -> Placement:
    """Placements come from the page; refuse values that would put NaN or mirrored art in a plot."""
    if not (math.isfinite(placement.x) and math.isfinite(placement.y)):
        raise ValueError(f"Placement position must be finite: {placement}")
    if not (math.isfinite(placement.scale) and 0 < placement.scale <= MAX_SCALE):
        raise ValueError(f"Placement scale must be above 0 and at most {MAX_SCALE:g}: {placement}")
    if placement.rotation not in ROTATIONS:
        raise ValueError(f"Placement rotation must be a multiple of 90 degrees: {placement}")
    return placement
```

- [ ] **Step 4: Write `src/rosetta/app/payloads.py`**

```python
"""Rosetta's objects as the plain JSON the page receives (documented in docs/bridge.md)."""
import base64

from rosetta.colors import color_name, is_white
from rosetta.compose import CLIP_WARNING_MM, Job, Material, Placement
from rosetta.models import MachineModel

DECIMALS = 2  # 0.01 mm: finer than any AxiDraw draws, and it keeps big files' JSON small


def _rounded(value: float) -> float:
    return round(value, DECIMALS)


def placement_payload(placement: Placement) -> dict:
    return {"x": placement.x, "y": placement.y, "scale": placement.scale, "rotation": placement.rotation}


def piece_payload(piece) -> dict:
    """A piece, with its lines in artwork mm (the page applies the placement itself while dragging)."""
    art = piece.artwork
    groups: dict[str, list] = {}
    for shape in art.shapes:
        lines = groups.setdefault(shape.color, [])
        for polyline in shape.polylines:
            lines.append([_rounded(value) for point in polyline for value in point])
    preview = None
    if art.preview_svg:
        encoded = base64.b64encode(art.preview_svg.encode("utf-8")).decode("ascii")
        preview = f"data:image/svg+xml;base64,{encoded}"
    return {
        "id": piece.id,
        "name": art.name,
        "path": piece.path,
        "page": piece.page,
        "width_mm": art.width_mm,
        "height_mm": art.height_mm,
        "placement": placement_payload(piece.placement),
        "issues": [
            {"code": issue.code, "message": issue.message, "count": issue.count} for issue in art.issues
        ],
        "groups": [
            {"color": color, "name": color_name(color), "white": is_white(color), "lines": lines}
            for color, lines in groups.items()
        ],
        "preview": preview,
    }


def material_payload(material: Material, model: MachineModel | None) -> dict:
    """The paper, plus the plotter's reach and whether the paper fits inside it (unknown without a model)."""
    reach = fits = None
    if model is not None:
        travel_x, travel_y = model.travel_mm
        reach = [travel_x, travel_y]
        fits = (
            material.x + material.width <= travel_x + CLIP_WARNING_MM
            and material.y + material.height <= travel_y + CLIP_WARNING_MM
        )
    return {
        "x": material.x, "y": material.y, "width": material.width, "height": material.height,
        "reach": reach, "fits": fits,
    }


def job_payload(job: Job) -> dict:
    """The pens a job needs, in plot order (the Pens panel)."""
    return {
        "colors": [
            {"layer": number, "color": group.color, "name": group.name, "lines": len(group.polylines)}
            for number, group in enumerate(job.groups, start=1)
        ],
        "ink_bbox": list(job.ink_bbox) if job.ink_bbox else None,
        "clipped": job.clipped,
        "empty": not job.groups,
    }
```

- [ ] **Step 5: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_session.py -v`
Expected: `13 passed`.

- [ ] **Step 6: Commit**

```powershell
git add src\rosetta\app\session.py src\rosetta\app\payloads.py tests\test_session.py
git commit -m "feat: session of pieces on paper, and its JSON for the page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `Machine`, part 1: connect, identify, Home

This answers the final review's "Machine connection owner" gap.
- One object owns the plotter connection, and only one request uses it at a time. A second request gets a polite "still busy" instead of waiting, except `request_stop()`, which works any time.
- **Detecting a pulled cable:** plotink answers an empty firmware string when the cable has been pulled. It does *not* answer "no power", because `queryVoltage` reports True when it can't read anything. So `scan()` checks the firmware to see if the plotter is still there.

**Files:**
- Modify: `src/rosetta/engine/plotter.py` (add `port_name`)
- Create: `src/rosetta/app/machine.py`, `tests/app_helpers.py`
- Test: `tests/test_machine.py`, `tests/test_plotter.py` (append)

- [ ] **Step 1: Write the test helpers**

`tests/app_helpers.py`:
```python
"""Helpers for the rosetta.app tests: a fake plotter that can be plugged in and out, and waiting."""
import time

from rosetta.app.machine import Machine
from rosetta.app.settings import SettingsStore
from rosetta.engine.plotter import Plotter
from tests.fake_ebb import interactive_factory


class Bench:
    """A test bench: plug a fake plotter in (bench.ebb = IFakeEBB(...)) or pull it out (bench.ebb = None).
    Every Plotter the Machine makes talks to whatever is plugged in at that moment."""

    def __init__(self, ebb=None):
        self.ebb = ebb

    def plotter(self) -> Plotter:
        return Plotter(factory=interactive_factory(self.ebb))


def make_machine(tmp_path, ebb=None):
    """(machine, bench, store): settings kept in tmp_path, and no real waiting for reboots."""
    bench = Bench(ebb)
    store = SettingsStore(tmp_path / "settings.json")
    machine = Machine(store, plotter_factory=bench.plotter, sleep=lambda _seconds: None)
    return machine, bench, store


def wait_for(condition, timeout: float = 10.0, interval: float = 0.01) -> None:
    """Wait until condition() is true; fail the test if it never is."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise AssertionError("timed out waiting")
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_plotter.py`:
```python
def test_port_name_reads_the_serial_port():
    plotter, _fakes = _connected()
    assert plotter.port_name() == "COM9"  # FakeAD's port is the plain name; a real one is a Serial object
```

`tests/test_machine.py`:
```python
"""Machine runs the real EMS interactive engine against fake EBBs (tests/fake_ebb.py)."""
import pytest

from rosetta.app.machine import BUSY, NEEDS_MODEL, NO_POWER, NOT_CONNECTED, MachineState
from rosetta.app.settings import SettingsStore
from rosetta.engine.options import Advanced
from rosetta.errors import UserProblem
from tests.app_helpers import make_machine
from tests.fake_ebb import IFakeEBB, skip_engine_waits


@pytest.fixture(autouse=True)
def fast_engine(monkeypatch):
    skip_engine_waits(monkeypatch)


def _plugged(tmp_path, **ebb_args):
    ebb = IFakeEBB(move_sleep=0, **ebb_args)
    machine, bench, store = make_machine(tmp_path, ebb)
    return machine, ebb, bench, store


def test_no_plotter(tmp_path):
    machine, _bench, _store = make_machine(tmp_path)
    assert machine.scan()["state"] == "no_plotter"


def test_a_named_plotter_is_recognized_and_its_carriage_freed(tmp_path):
    machine, ebb, _bench, _store = _plugged(tmp_path, nickname="PSU Lab m5p1")
    status = machine.scan()
    assert status["state"] == "not_homed"
    assert (status["model"], status["model_name"], status["label"]) == (5, "AxiDraw SE/A1", "PSU Lab")
    assert status["power_ok"] is True and "2.8.1" in status["firmware"]
    assert "EM,0,0" in ebb.log  # motors off: the carriage slides by hand
    assert machine.profile_key() == "PSU Lab m5p1"


def test_an_unnamed_plotter_needs_its_model(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path)
    status = machine.scan()
    assert (status["state"], status["model"]) == ("needs_model", None)
    with pytest.raises(UserProblem, match=NEEDS_MODEL):
        machine.set_home()


def test_a_missing_power_adapter_is_reported(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m1p1", voltage=0)
    assert machine.scan()["power_ok"] is False
    with pytest.raises(UserProblem, match=NO_POWER):
        machine.set_home()


def test_identify_names_the_plotter_and_reconnects(tmp_path):
    machine, ebb, _bench, _store = _plugged(tmp_path)
    machine.scan()
    status = machine.identify(5, 1, "PSU Lab")
    assert ebb.nickname == "PSU Lab m5p1"
    assert (status["state"], status["model"], status["nickname"]) == ("not_homed", 5, "PSU Lab m5p1")


def test_identify_on_old_firmware_remembers_the_model_on_this_laptop(tmp_path):
    machine, ebb, _bench, store = _plugged(tmp_path, version="2.4.0")
    ebb.port = "COM7"  # what Plotter.port_name() reads from a real serial port
    machine.scan()
    status = machine.identify(3, 1, "")
    assert (status["state"], status["model"], status["old_firmware"]) == ("not_homed", 3, True)
    assert SettingsStore(store.path).settings.old_firmware["COM7"].model == 3
    assert machine.profile_key() == "port:COM7"


def test_home_makes_the_position_known(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m5p1")
    machine.scan()
    assert machine.set_home()["position"] == [0.0, 0.0]
    status = machine.motors_off()
    assert (status["state"], status["position"]) == ("not_homed", None)


def test_a_busy_plotter_turns_a_second_request_away(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m5p1")
    machine.scan()
    machine._lock.acquire()  # as if a long move were running
    try:
        with pytest.raises(UserProblem, match=BUSY):
            machine.set_home()
        assert machine.scan()["state"] == "not_homed"  # a look while busy just reports
    finally:
        machine._lock.release()


def test_a_pulled_cable_is_noticed(tmp_path):
    machine, ebb, bench, _store = _plugged(tmp_path, nickname="m5p1")
    machine.scan()
    ebb.dead = True
    bench.ebb = None
    assert machine.scan()["state"] == "no_plotter"


def test_pen_settings_are_kept_without_a_plotter(tmp_path):
    machine, _bench, _store = make_machine(tmp_path)
    status = machine.set_pen(45, "marker")
    assert (status["pen_down"], status["pen_type"]) == (45, "marker")
    with pytest.raises(ValueError):
        machine.set_pen(81, "marker")


def test_a_pen_height_too_close_to_the_advanced_pen_up_is_refused(tmp_path):
    machine, _bench, _store = make_machine(tmp_path)
    machine.advanced = Advanced(pen_up=50)
    with pytest.raises(UserProblem, match="at least 10 above"):
        machine.set_pen(45, "fineliner")


def test_plot_settings_need_a_known_plotter(tmp_path):
    machine, _bench, _store = make_machine(tmp_path)
    with pytest.raises(UserProblem, match=NOT_CONNECTED):
        machine.plot_settings()


def test_shutdown_lets_go(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m5p1")
    machine.scan()
    machine.set_home()
    machine.shutdown()
    assert machine.state is MachineState.NO_PLOTTER
```

- [ ] **Step 3: Run them to make sure they fail**

Run: `.venv\Scripts\python -m pytest tests\test_machine.py tests\test_plotter.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'rosetta.app.machine'`.

- [ ] **Step 4: Add `port_name` to `Plotter` in `src/rosetta/engine/plotter.py`**

Put it after `nickname()`:
```python
    def port_name(self) -> str | None:
        """The serial port's name (e.g. "COM3"), or None if it can't be told."""
        port = self._port()
        return port if isinstance(port, str) else getattr(port, "port", None)
```

- [ ] **Step 5: Write `src/rosetta/app/machine.py`**

```python
"""The one owner of the plotter connection (spec §6.1).

Steps 1-4 move the plotter through the EMS interactive context. A plot run takes the USB port with
release_for_plot() and gives it back with after_plot(). Only one request uses the plotter at a time:
a second one gets a "still busy" message instead of waiting, except request_stop(), which works any time.
"""
import contextlib
import logging
import threading
import time
from enum import Enum

from rosetta.app.settings import StoredIdentity
from rosetta.engine.identity import Identity, encode_nickname
from rosetta.engine.options import MIN_PEN_TRAVEL, PEN_DOWN_MAX, Advanced, PlotSettings
from rosetta.engine.plotter import IdentityWrite, Plotter, PlotterStopped
from rosetta.errors import UserProblem
from rosetta.models import PEN_TYPES, get_model

logger = logging.getLogger(__name__)

REBOOT_WAIT_S = 3.0  # the board restarts after its name is written
RECONNECT_TRIES = 10
RECONNECT_PAUSE_S = 1.0
SHUTDOWN_WAIT_S = 10.0

BUSY = "The plotter is still busy. Wait for it to finish, then try again."
NOT_CONNECTED = "No plotter is connected. Plug in the USB cable and the power adapter."
NEEDS_MODEL = "Choose which AxiDraw this is first."
NOT_HOMED = ("Slide the pen to the corner next to the HOME label and the USB port, "
             "then click It's in the corner.")
PLOTTING = "The plotter is plotting. Pause or stop the plot first."
STOPPED_MOVING = ("The plotter stopped before the move finished. Slide the pen Home, "
                  "then click It's in the corner.")
NO_POWER = "The power adapter isn't plugged in. The pen can't move without it."
NAME_NOT_SAVED = "The plotter didn't accept its new name. Check the USB cable and try again."
NO_RETURN = ("The plotter didn't come back after saving its name. Unplug the USB cable, "
             "plug it back in, and try again.")


class MachineState(Enum):
    NO_PLOTTER = "no_plotter"
    NEEDS_MODEL = "needs_model"  # connected, but which AxiDraw it is isn't known
    NOT_HOMED = "not_homed"  # connected and known, but where the pen is isn't
    READY = "ready"  # homed: the pen's position is known
    PLOTTING = "plotting"  # a plot run has the USB port


_REFUSALS = {
    MachineState.NO_PLOTTER: NOT_CONNECTED,
    MachineState.NEEDS_MODEL: NEEDS_MODEL,
    MachineState.NOT_HOMED: NOT_HOMED,
    MachineState.READY: BUSY,
    MachineState.PLOTTING: PLOTTING,
}
_CONNECTED = (MachineState.NEEDS_MODEL, MachineState.NOT_HOMED, MachineState.READY)
_KNOWN = (MachineState.NOT_HOMED, MachineState.READY)


class Machine:
    def __init__(self, store, plotter_factory=Plotter, sleep=time.sleep):
        self._store = store  # SettingsStore: models remembered for old firmware
        self._new_plotter = plotter_factory
        self._sleep = sleep
        self._lock = threading.Lock()
        self._plotter: Plotter | None = None
        self.state = MachineState.NO_PLOTTER
        self.identity: Identity | None = None
        self.firmware = ""
        self.nickname: str | None = None
        self.port: str | None = None
        self.power_ok = False
        self.old_firmware = False
        self.position = (0.0, 0.0)
        self.pen_down = 30
        self.pen_type = "fineliner"
        self.advanced = Advanced()

    # What the page sees.

    def status(self) -> dict:
        identity = self.identity
        return {
            "state": self.state.value,
            "firmware": self.firmware,
            "power_ok": self.power_ok,
            "model": identity.model if identity else None,
            "model_name": get_model(identity.model).name if identity else None,
            "penlift": identity.penlift if identity else None,
            "label": identity.label if identity else None,
            "nickname": self.nickname,
            "old_firmware": self.old_firmware,
            "position": list(self.position) if self.state is MachineState.READY else None,
            "pen_down": self.pen_down,
            "pen_type": self.pen_type,
        }

    def plot_settings(self) -> PlotSettings:
        if self.identity is None:
            raise UserProblem(NOT_CONNECTED)
        return self._settings()

    def profile_key(self) -> str | None:
        """Where this plotter's pen settings are kept: its nickname, or its port on old firmware."""
        if self.identity is None:
            return None
        if self.old_firmware:
            return f"port:{self.port}" if self.port else None
        return self.nickname

    # Step 1: connect, identify, Home.

    def scan(self) -> dict:
        """Look for the plotter, or check the connected one is still there. Never raises."""
        if not self._lock.acquire(blocking=False):
            return self.status()  # something is using it, so it's plainly there
        try:
            if self.state is MachineState.PLOTTING:
                return self.status()
            if self._plotter is not None and not self._still_there():
                self._drop()
            if self._plotter is None:
                self._connect_and_identify()
            return self.status()
        finally:
            self._lock.release()

    def identify(self, model: int, penlift: int, label: str) -> dict:
        """Store which AxiDraw this is (spec §8): in its nickname, or on this laptop if the firmware is
        too old. Returns the status after reconnecting; its nickname echoes what the plotter stored."""
        identity = Identity(model, penlift, label)
        encode_nickname(identity)  # ValueError for an unknown model or pen lift, before anything is written
        with self._using(*_CONNECTED) as plotter:
            port = self.port
            result = plotter.write_identity(identity)  # always ends the connection
            self._plotter = None
            if result is IdentityWrite.WRITTEN:
                self._sleep(REBOOT_WAIT_S)
            elif result is not IdentityWrite.FAILED and port:
                self._store.settings.old_firmware[port] = StoredIdentity(model, penlift, label)
                self._store.save()
            else:
                self._forget()
                raise UserProblem(NAME_NOT_SAVED)
            for _attempt in range(RECONNECT_TRIES):
                self._connect_and_identify()
                if self._plotter is not None:
                    return self.status()
                self._sleep(RECONNECT_PAUSE_S)
            raise UserProblem(NO_RETURN)

    def motors_off(self) -> dict:
        """Let go of the carriage so the student can slide the pen Home (the start of Home and Re-home)."""
        with self._using(*_KNOWN) as plotter:
            plotter.motors_off()
            self.state = MachineState.NOT_HOMED
        return self.status()

    def set_home(self) -> dict:
        """The student says the pen is in the Home corner: from now on it's (0, 0)."""
        with self._using(*_KNOWN) as plotter:
            self._check_power(plotter)
            try:
                plotter.set_home()
            except RuntimeError as lost:  # Plotter.set_home couldn't reconnect
                self._drop()
                raise UserProblem(NOT_CONNECTED, details=str(lost)) from lost
            self.position = (0.0, 0.0)
            self.state = MachineState.READY
        return self.status()

    # Step 4: the pen.

    def set_pen(self, pen_down: int, pen_type: str) -> dict:
        """The Pen step's height slider and pen type. A connected pen moves to the new height at once."""
        if isinstance(pen_down, bool) or not isinstance(pen_down, int) or not 0 <= pen_down <= PEN_DOWN_MAX:
            raise ValueError(f"Pen-down height must be a whole number from 0 to {PEN_DOWN_MAX}.")
        if pen_type not in PEN_TYPES:
            raise ValueError(f"Unknown pen type: {pen_type!r}")
        pen_up = self.advanced.pen_up
        if pen_up is not None and pen_up - pen_down < MIN_PEN_TRAVEL:
            raise UserProblem(
                f"The pen-up height under Advanced ({pen_up}) must be at least {MIN_PEN_TRAVEL} above "
                "the pen-down height."
            )
        if self._plotter is not None and self.state in _KNOWN:
            with self._using(*_KNOWN) as plotter:
                plotter.set_pen_down_height(pen_down)
        self.pen_down, self.pen_type = pen_down, pen_type
        return self.status()

    # Any time.

    def request_stop(self) -> None:
        """Stop a move in progress at its next step, pen up. Safe from any thread, busy or not."""
        plotter = self._plotter
        if plotter is not None:
            plotter.request_pause()

    def shutdown(self) -> None:
        """The app is closing: stop any move, lift the pen and let go of the USB port."""
        self.request_stop()
        if self._lock.acquire(timeout=SHUTDOWN_WAIT_S):
            try:
                self._drop()
            finally:
                self._lock.release()

    # Inside.

    @contextlib.contextmanager
    def _using(self, *allowed: MachineState):
        """One request at a time, in a state that allows it. A move that stops partway (Stop, the pause
        button, a pulled cable) leaves the pen's position unknown."""
        if not self._lock.acquire(blocking=False):
            raise UserProblem(BUSY)
        try:
            if self.state not in allowed:
                raise UserProblem(_REFUSALS[self.state])
            yield self._plotter
        except PlotterStopped as stopped:
            self._after_stop()
            raise UserProblem(STOPPED_MOVING, details=str(stopped)) from stopped
        finally:
            self._lock.release()

    def _after_stop(self) -> None:
        """EMS ignores moves after a stop, so start a fresh connection; it frees the carriage for re-homing."""
        self._drop()
        self._connect_and_identify()

    def _check_power(self, plotter: Plotter) -> None:
        self.power_ok = plotter.power_ok()
        if not self.power_ok:
            raise UserProblem(NO_POWER)

    def _settings(self) -> PlotSettings:
        identity = self.identity
        return PlotSettings(
            model=identity.model if identity else 1,
            penlift=identity.penlift if identity else 1,
            pen_down=self.pen_down,
            pen_type=self.pen_type,
            advanced=self.advanced,
        )

    def _still_there(self) -> bool:
        """plotink answers an empty firmware version once the USB cable has been pulled."""
        try:
            if not self._plotter.firmware():
                return False
            self.power_ok = self._plotter.power_ok()
            return True
        except Exception:
            logger.info("The plotter stopped answering", exc_info=True)
            return False

    def _connect_and_identify(self) -> None:
        """Open the plotter, learn which it is, and free its carriage. NO_PLOTTER if it isn't there."""
        plotter = self._new_plotter()
        if not plotter.connect(self._settings()):
            self._forget()
            return
        try:
            self.firmware = plotter.firmware()
            self.power_ok = plotter.power_ok()
            self.port = plotter.port_name()
            self.nickname = plotter.nickname()
            identity = plotter.read_identity()
            self.old_firmware = False
            stored = self._store.settings.old_firmware.get(self.port) if self.port else None
            if identity is None and stored is not None:
                identity = Identity(stored.model, stored.penlift, stored.label)
                self.old_firmware = True
            self.identity = identity
            if identity is not None:
                plotter.disconnect()  # reconnect with this model's reach, so moves stay inside it
                if not plotter.connect(self._settings()):
                    self._forget()
                    return
            plotter.motors_off()  # connecting holds the carriage; the student is about to slide it Home
        except PlotterStopped:
            plotter.disconnect()
            self._forget()
            return
        self._plotter = plotter
        self.state = MachineState.NOT_HOMED if identity is not None else MachineState.NEEDS_MODEL

    def _drop(self) -> None:
        plotter, self._plotter = self._plotter, None
        if plotter is not None:
            try:
                plotter.disconnect()
            except Exception:
                logger.info("Couldn't close the plotter's connection", exc_info=True)
        self._forget()

    def _forget(self) -> None:
        self.state = MachineState.NO_PLOTTER
        self.identity = None
        self.firmware = ""
        self.nickname = None
        self.port = None
        self.power_ok = False
        self.old_firmware = False
```

- [ ] **Step 6: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_machine.py tests\test_plotter.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add src\rosetta\engine\plotter.py src\rosetta\app\machine.py tests\app_helpers.py tests\test_machine.py tests\test_plotter.py
git commit -m "feat: Machine owns the plotter connection: connect, identify, Home" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: `Machine`, part 2: moves, and handing over to a plot

**Files:**
- Modify: `src/rosetta/app/machine.py`
- Test: `tests/test_machine.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_machine.py`:
```python
def _ready(tmp_path, **ebb_args):
    machine, ebb, bench, _store = _plugged(tmp_path, nickname="Lab m1p1", **ebb_args)
    machine.scan()
    machine.set_home()
    return machine, ebb, bench


def test_goto_and_jog(tmp_path):
    machine, _ebb, _bench = _ready(tmp_path)
    assert machine.goto(50, 20)["position"] == pytest.approx([50, 20])
    assert machine.jog(-10, 5)["position"] == pytest.approx([40, 25])


def test_moves_wait_for_home(tmp_path):
    machine, _ebb, _bench, _store = _plugged(tmp_path, nickname="m1p1")
    machine.scan()
    with pytest.raises(UserProblem, match="HOME label"):
        machine.goto(10, 10)


def test_pen_up_and_down(tmp_path):
    machine, ebb, _bench = _ready(tmp_path)
    machine.pen(True)
    assert ebb.pen_cmds[-1][0] == "down"
    machine.pen(False)
    assert ebb.pen_cmds[-1][0] == "up"


def test_trace_and_test_mark_end_at_home(tmp_path):
    machine, ebb, _bench = _ready(tmp_path)
    machine.goto(30, 30)
    assert machine.trace((10, 10, 60, 40))["position"] == [0.0, 0.0]
    moves = ebb.sm
    assert machine.test_mark(0, 0)["position"] == [0.0, 0.0]
    assert ebb.sm > moves and any(state == "down" for state, _count in ebb.pen_cmds)


def test_a_stopped_move_means_home_is_unknown(tmp_path):
    machine, _ebb, _bench = _ready(tmp_path, button_after_moves=1)  # the plotter's pause button
    with pytest.raises(UserProblem, match="stopped before the move finished"):
        machine.goto(100, 100)
    assert machine.state is MachineState.NOT_HOMED


def test_stop_ends_a_move(tmp_path):
    machine, ebb, _bench = _ready(tmp_path)
    ebb.on_sm = lambda count: count == 3 and machine.request_stop()
    with pytest.raises(UserProblem):
        machine.goto(200, 150)
    assert machine.state is MachineState.NOT_HOMED


def test_the_plotter_is_handed_over_for_a_plot_and_taken_back(tmp_path):
    machine, _ebb, _bench = _ready(tmp_path)
    machine.goto(30, 30)
    settings = machine.release_for_plot()
    assert machine.state is MachineState.PLOTTING and settings.model == 1
    with pytest.raises(UserProblem, match="plotting"):
        machine.goto(5, 5)
    assert machine.after_plot(at_home=True)["state"] == "ready"
    machine.release_for_plot()
    assert machine.after_plot(at_home=False)["state"] == "not_homed"


def test_a_plot_needs_the_power_adapter(tmp_path):
    machine, ebb, _bench = _ready(tmp_path)
    ebb.voltage = 0
    with pytest.raises(UserProblem, match=NO_POWER):
        machine.release_for_plot()
    assert machine.state is MachineState.READY


def test_motors_can_be_released_while_a_plot_is_stopped(tmp_path):
    machine, _ebb, bench = _ready(tmp_path)
    machine.release_for_plot()
    assert machine.release_motors() is True
    bench.ebb = None
    assert machine.release_motors() is False
    assert machine.state is MachineState.PLOTTING
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `.venv\Scripts\python -m pytest tests\test_machine.py -v`
Expected: the new tests fail with `AttributeError: 'Machine' object has no attribute 'goto'` (and `pen`, `trace`, `release_for_plot`...).

- [ ] **Step 3: Add the methods**

In `src/rosetta/app/machine.py`, add this section to `Machine`, between `set_pen` and the `# Any time.` section:
```python
    # Steps 2-5: moves.

    def goto(self, x: float, y: float) -> dict:
        """Pen-up move to (x, y) mm from Home, kept inside the plotter's reach."""
        with self._using(MachineState.READY) as plotter:
            self._check_power(plotter)
            plotter.goto(float(x), float(y))
            self.position = plotter.position()
        return self.status()

    def jog(self, dx: float, dy: float) -> dict:
        """The Material step's arrow buttons: a pen-up nudge."""
        with self._using(MachineState.READY) as plotter:
            self._check_power(plotter)
            plotter.jog(float(dx), float(dy))
            self.position = plotter.position()
        return self.status()

    def pen(self, down: bool) -> dict:
        """Raise or lower the pen where it is (the Pen step's buttons)."""
        with self._using(*_KNOWN) as plotter:
            self._check_power(plotter)
            if down:
                plotter.pen_down()
            else:
                plotter.pen_up()
        return self.status()

    def trace(self, rect) -> dict:
        """Pen up around rect (everything that will be drawn), then Home (spec §5, step 5)."""
        x0, y0, x1, y1 = (float(value) for value in rect)
        with self._using(MachineState.READY) as plotter:
            self._check_power(plotter)
            plotter.trace((x0, y0, x1, y1))
            self.position = (0.0, 0.0)
        return self.status()

    def test_mark(self, corner_x: float, corner_y: float) -> dict:
        """A 10 mm line just inside the paper corner nearest Home, then back Home (spec §5, step 4)."""
        with self._using(MachineState.READY) as plotter:
            self._check_power(plotter)
            plotter.test_mark(float(corner_x), float(corner_y))
            self.position = (0.0, 0.0)
        return self.status()

    # Step 5: handing the plotter to a plot run and taking it back.

    def release_for_plot(self) -> PlotSettings:
        """Check the power, return Home and let go of the USB port. Returns the settings to plot with:
        the plot keeps them, so its resume uses the same ones (plan2-notes.md)."""
        with self._using(MachineState.READY) as plotter:
            self._check_power(plotter)
            settings = self.plot_settings()
            plotter.release_for_plot()
            self._plotter = None
            self.state = MachineState.PLOTTING
        return settings

    def after_plot(self, at_home: bool) -> dict:
        """Take the plotter back after a plot. at_home: the pen is known to be Home (the plot finished,
        or it was sent Home); otherwise the motors go off so the pen can be slid Home by hand."""
        with self._using(MachineState.PLOTTING):
            plotter = self._new_plotter()
            if not plotter.connect(self._settings()):
                self._forget()
                return self.status()
            try:
                if not at_home:
                    plotter.motors_off()
            except PlotterStopped:
                plotter.disconnect()
                self._forget()
                return self.status()
            self._plotter = plotter
            self.state = MachineState.READY if at_home else MachineState.NOT_HOMED
            self.position = (0.0, 0.0)
        return self.status()

    def release_motors(self) -> bool:
        """While a plot is stopped by a lost cable or an error: switch the motors off so the carriage can
        be slid Home by hand. False if the plotter can't be reached."""
        with self._using(MachineState.PLOTTING):
            plotter = self._new_plotter()
            try:
                if not plotter.connect(self._settings()):
                    return False
                plotter.motors_off()
                return True
            except Exception:  # a plotter that vanishes again is "not released", not a crash
                logger.info("Couldn't switch the motors off", exc_info=True)
                return False
            finally:
                plotter.disconnect()
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_machine.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\app\machine.py tests\test_machine.py
git commit -m "feat: Machine moves, trace, test mark, and plot handover" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Events from Python to the page

Spec §6.5: long operations push progress events to the page. `plan2-notes.md` adds that the progress callback must never block, because it runs on the engine's poller thread.
- `WindowSink` queues each event and sends it from its own thread.
- If several `plot_progress` events are waiting, only the newest is sent.
- The page defines `window.rosettaEvent(name, data)`.

**Files:**
- Create: `src/rosetta/app/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing test**

`tests/test_events.py`:
```python
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
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python -m pytest tests\test_events.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'rosetta.app.events'`.

- [ ] **Step 3: Write `src/rosetta/app/events.py`**

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_events.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\app\events.py tests\test_events.py
git commit -m "feat: non-blocking events from Python to the page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: `PlotController`, part 1: prepare, trace, and plot pen by pen

This answers the final review's "plot-session controller" gap. It does what the CLI's `_PlotRun` does, but it is driven by events instead of `input()`.

Every state change goes to the page as a `plot_state` event carrying `status()`. That status lists the `actions` the page should offer as buttons. The states:

| State | Means | Actions |
|---|---|---|
| `idle` | nothing prepared | (none) |
| `ready` | prepared: summary, preview path, warnings | `trace`, `start` |
| `tracing` | pen-up outline in progress | `stop` |
| `load_pen` | waiting for pen *k* in the holder | `continue`, `cancel` |
| `plotting` | a layer is drawing | `pause` |
| `pausing` | pause asked, engine stopping | (none) |
| `paused` | pen up where it stopped | `resume`, `home`, `cancel` |
| `homing` | Return Home in progress | `pause` |
| `paused_at_home` | paused with the pen Home | `resume`, `cancel` |
| `reconnect` | cable lost or engine error: plug back in | `reconnect`, `cancel` |
| `slide_home` | slide the pen Home by hand | `rehomed`, `cancel` |
| `not_connected` | a run couldn't find the plotter; nothing moved | `retry`, `cancel` |
| `done` | finished, pen Home | `start` (Plot another copy), `trace` |

**Files:**
- Create: `src/rosetta/app/plotjob.py`
- Test: `tests/test_plotjob.py`

- [ ] **Step 1: Write the failing test**

`tests/test_plotjob.py`:
```python
"""PlotController runs the real EMS engine: the Machine against one fake EBB, plot runs against another."""
import pytest

from rosetta.app.events import RecordingSink
from rosetta.app.plotjob import CLIPPED, NOTHING_TO_PLOT, PREPARE_FIRST, PlotController
from rosetta.app.session import Session
from rosetta.compose import Material
from rosetta.engine.runner import PlotRunner
from rosetta.errors import UserProblem
from tests.app_helpers import make_machine, wait_for
from tests.fake_ebb import FakeEBB, IFakeEBB, fake_factory, skip_engine_waits

LETTER = Material(0.0, 0.0, 279.4, 215.9)
ONE_COLOR = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">
<path d="M10 10 H90 V50 H10 Z" stroke="#000000" fill="none"/>
</svg>"""
TWO_COLORS = ONE_COLOR.replace("</svg>", '<path d="M20 30 H80" stroke="#ff0000" fill="none"/></svg>')


@pytest.fixture(autouse=True)
def fast_engine(monkeypatch):
    skip_engine_waits(monkeypatch)


class Rig:
    """A homed Machine on one fake plotter, plot runs on another, and a controller over both.
    Replace rig.run_ebb to change what the next plot run finds (None: no plotter at all)."""

    def __init__(self, tmp_path, drawing=ONE_COLOR, run_ebb=None):
        self.plotter_ebb = IFakeEBB(nickname="Lab m1p1", move_sleep=0)
        self.machine, self.bench, _store = make_machine(tmp_path, self.plotter_ebb)
        self.machine.scan()
        self.machine.set_home()
        self.session = Session(LETTER)
        art = tmp_path / "art.svg"
        art.write_text(drawing, encoding="utf-8")
        self.session.add(art)
        self.run_ebb = run_ebb or FakeEBB(move_sleep=0)
        self.sink = RecordingSink()
        runner = PlotRunner(factory=lambda: fake_factory(self.run_ebb)(), poll_interval=0.001)
        self.controller = PlotController(self.machine, self.session, self.sink, runner_factory=lambda: runner)

    def state(self) -> str:
        return self.controller.status()["state"]

    def wait_until(self, state: str) -> None:
        wait_for(lambda: self.state() == state)


def test_prepare_plans_every_pen(tmp_path):
    rig = Rig(tmp_path, TWO_COLORS)
    summary = rig.controller.prepare()
    assert [(layer["layer"], layer["name"]) for layer in summary["layers"]] == [(1, "black"), (2, "red")]
    assert summary["total_seconds"] > 0
    assert summary["layers"][0]["path"][0]["down"] is False  # it sets off from Home, pen up
    assert rig.state() == "ready"
    assert rig.sink.named("plot_state")[-1]["actions"] == ["trace", "start"]


def test_prepare_with_nothing_on_the_paper(tmp_path):
    rig = Rig(tmp_path)
    rig.session.clear()
    with pytest.raises(UserProblem, match=NOTHING_TO_PLOT):
        rig.controller.prepare()


def test_prepare_warns_about_lines_off_the_paper(tmp_path):
    rig = Rig(tmp_path)
    rig.session.place(rig.session.pieces[0].id, 250, 10, 1, 0)  # hangs off the paper's far edge
    assert CLIPPED in rig.controller.prepare()["warnings"]


def test_a_one_pen_plot_runs_to_done(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.controller.start()
    rig.wait_until("done")
    assert rig.run_ebb.sm > 0
    assert rig.machine.status()["state"] == "ready"
    progress = rig.sink.named("plot_progress")
    assert progress and progress[-1]["fraction"] == pytest.approx(1.0, abs=0.01)


def test_each_pen_is_asked_for(tmp_path):
    rig = Rig(tmp_path, TWO_COLORS)
    rig.controller.prepare()
    rig.controller.start()
    assert rig.state() == "load_pen" and "black pen" in rig.controller.status()["message"]
    rig.controller.continue_pen()
    rig.wait_until("load_pen")
    assert "red pen in the holder (2 of 2)" in rig.controller.status()["message"]
    rig.controller.continue_pen()
    rig.wait_until("done")


def test_plot_another_copy(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.controller.start()
    rig.wait_until("done")
    moves = rig.run_ebb.sm
    rig.controller.start()
    wait_for(lambda: rig.run_ebb.sm > moves and rig.state() == "done")


def test_no_power_means_no_plot(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.plotter_ebb.voltage = 0
    with pytest.raises(UserProblem, match="power adapter"):
        rig.controller.start()
    assert rig.state() == "ready"


def test_changes_make_the_prepared_plot_stale(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.controller.invalidate()
    assert rig.state() == "idle"
    with pytest.raises(UserProblem, match=PREPARE_FIRST):
        rig.controller.start()


def test_trace_goes_around_the_drawing_and_home(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    moves = rig.plotter_ebb.sm
    assert rig.controller.trace()["position"] == [0.0, 0.0]
    assert rig.plotter_ebb.sm > moves and rig.state() == "ready"


def test_a_run_that_finds_no_plotter_has_moved_nothing(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.run_ebb = None
    rig.controller.start()
    rig.wait_until("not_connected")
    assert rig.controller.status()["actions"] == ["retry", "cancel"]
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python -m pytest tests\test_plotjob.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'rosetta.app.plotjob'`.

- [ ] **Step 3: Write `src/rosetta/app/plotjob.py`**

```python
"""Step 5, Plot (spec §5, §7, §10): prepare the job, trace it, and plot it one pen color at a time,
through pen changes, pauses, lost cables and re-homing.

Each state change goes to the page as a "plot_state" event (the status() dict); the pen's live position
as "plot_progress". Engine runs happen on a worker thread, so the page's buttons return at once.
From plan2-notes.md: never estimate while plotting; a pause asked for before a run listens is asked
again; any mid-run error means the pen's position is unknown; a resume uses the settings its plot
started with; the progress callback never blocks.
"""
import logging
import threading
from dataclasses import dataclass

from rosetta.engine.options import PlotSettings
from rosetta.engine.preview import Run, plan_layer
from rosetta.engine.runner import PlotOutcome, PlotResult, PlotRunner
from rosetta.errors import UserProblem
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg

logger = logging.getLogger(__name__)

MANY_COLORS = 10  # from this many pens, say how many pen changes are coming
MAX_COLORS = 1000  # EMS plots layers 1-1000
WORKER_JOIN_S = 30.0

NOTHING_TO_PLOT = "Nothing to plot: no lines land on the paper."
TOO_MANY_COLORS = ("This drawing has more than 1000 colors. Reduce the colors in your design app, "
                   "then import it again.")
FINISH_FIRST = "Finish or cancel the current plot first."
PREPARE_FIRST = "Open the Plot step again to get the plot ready."
NOT_NOW = "That can't be done right now."
CLIPPED = "Some lines hang off the paper or out of the plotter's reach. Those parts won't be drawn."
DONE = "Done! The pen is back Home."
SLIDE_HOME = ("Slide the pen to the corner next to the HOME label and the USB port, "
              "then click It's in the corner.")
HOME_UNKNOWN = "Slide the pen Home before the next plot."
UNEXPECTED = "The plot stopped unexpectedly."

ACTIONS = {
    "idle": [],
    "ready": ["trace", "start"],
    "tracing": ["stop"],
    "load_pen": ["continue", "cancel"],
    "plotting": ["pause"],
    "pausing": [],
    "paused": ["resume", "home", "cancel"],
    "homing": ["pause"],
    "paused_at_home": ["resume", "cancel"],
    "reconnect": ["reconnect", "cancel"],
    "slide_home": ["rehomed", "cancel"],
    "not_connected": ["retry", "cancel"],
    "done": ["start", "trace"],
}
_AT_REST = ("idle", "ready", "done")


@dataclass(frozen=True)
class Layer:
    number: int  # the plot SVG's layer, from 1
    color: str
    name: str
    seconds: float
    pendown_mm: float
    runs: list[Run]


@dataclass(frozen=True)
class Prepared:
    svg: str
    layers: list[Layer]
    ink_bbox: tuple[float, float, float, float]
    warnings: list[str]


class PlotController:
    def __init__(self, machine, session, sink, runner_factory=PlotRunner, planner=plan_layer):
        self._machine = machine
        self._session = session
        self._sink = sink
        self._runner = runner_factory()
        self._plan = planner
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._prepared: Prepared | None = None
        self._state = "idle"
        self._message = ""
        self._details = ""
        self._index = 0  # the layer being plotted (0-based)
        self._settings: PlotSettings | None = None  # what this plot started with; its resume uses them too
        self._resume_svg: str | None = None
        self._at_home = True  # is the pen known to be at Home?
        self._was_at_home = True  # ...before the current run (a run that never connected moved nothing)
        self._retry_resume = False
        self._pause_wanted = False

    # What the page sees.

    def status(self) -> dict:
        prepared, index = self._prepared, self._index
        layer = prepared.layers[index] if prepared and index < len(prepared.layers) else None
        return {
            "state": self._state,
            "actions": list(ACTIONS[self._state]),
            "layer": index,
            "layers": len(prepared.layers) if prepared else 0,
            "color": layer.color if layer else None,
            "name": layer.name if layer else None,
            "message": self._message,
            "details": self._details,
        }

    def busy(self) -> bool:
        """Is a plot (or a trace) under way? Closing the app then needs asking first."""
        return self._state not in _AT_REST

    def summary(self) -> dict:
        """The prepared plot: per-pen times, warnings, and the planned path to animate."""
        prepared = self._prepared
        if prepared is None:
            raise UserProblem(PREPARE_FIRST)
        return {
            "layers": [
                {
                    "layer": layer.number,
                    "color": layer.color,
                    "name": layer.name,
                    "seconds": round(layer.seconds, 1),
                    "pendown_mm": round(layer.pendown_mm, 1),
                    "path": [
                        {"down": run.down, "points": [round(value, 2) for point in run.points for value in point]}
                        for run in layer.runs
                    ],
                }
                for layer in prepared.layers
            ],
            "total_seconds": round(sum(layer.seconds for layer in prepared.layers), 1),
            "ink_bbox": list(prepared.ink_bbox),
            "warnings": list(prepared.warnings),
        }

    # Getting ready.

    def prepare(self) -> dict:
        """Compose the job and plan every layer: slow for big drawings, so the page awaits it with a
        spinner. Refused while a plot is under way (an estimate's CPU load would fight its timing)."""
        with self._lock:
            if self._state not in _AT_REST:
                raise UserProblem(FINISH_FIRST)
        settings = self._machine.plot_settings()
        model = get_model(settings.model)
        job = self._session.compose(model)
        if not job.groups:
            raise UserProblem(NOTHING_TO_PLOT)
        if len(job.groups) > MAX_COLORS:
            raise UserProblem(TOO_MANY_COLORS)
        svg = plot_svg(model, job.groups)
        layers = []
        for number, group in enumerate(job.groups, start=1):
            plan = self._plan(svg, number, settings)
            layers.append(Layer(number, group.color, group.name, plan.seconds, plan.pendown_m * 1000, plan.runs))
        prepared = Prepared(svg, layers, job.ink_bbox, self._warnings(job.clipped, len(layers)))
        with self._lock:
            if self._state not in _AT_REST:
                raise UserProblem(FINISH_FIRST)
            self._prepared = prepared
            self._index = 0
            self._set("ready")
        return self.summary()

    def invalidate(self) -> None:
        """The drawing, paper or pen changed, so the prepared plot is out of date. Ignored mid-plot:
        the running plot keeps its own copy."""
        with self._lock:
            if self._state in _AT_REST:
                self._prepared = None
                self._index = 0
                if self._state != "idle":
                    self._set("idle")

    def trace(self) -> dict:
        """Pen up around everything that will be drawn, then Home. Blocks until done; Stop ends it."""
        with self._lock:
            self._need_prepared()
            box = self._prepared.ink_bbox
            self._set("tracing")
        try:
            return self._machine.trace(box)
        finally:
            with self._lock:
                self._set("ready")

    # Plotting.

    def start(self) -> None:
        """Start the prepared plot (also "Plot another copy"). The pen goes Home and the plot takes over
        the USB port; with several pens, the first one is asked for before anything is drawn."""
        with self._lock:
            self._need_prepared()
            self._settings = self._machine.release_for_plot()  # checks power, returns Home; may refuse
            self._index = 0
            self._resume_svg = None
            self._at_home = True
            if len(self._prepared.layers) > 1:
                self._ask_for_pen()
            else:
                self._run_layer(resume=False)

    def continue_pen(self) -> None:
        """The student has put the asked-for pen in the holder."""
        with self._lock:
            self._expect("load_pen")
            self._run_layer(resume=False)

    def shutdown(self) -> None:
        """The app is closing: pause a running plot (pen up) and wait for the engine to let go."""
        with self._lock:
            if self._state in ("plotting", "homing"):
                self._pause_wanted = True
                self._runner.pause()
            worker = self._worker
        if worker is not None:
            worker.join(WORKER_JOIN_S)

    # Inside.

    def _set(self, state: str, message: str = "", details: str = "") -> None:
        self._state, self._message, self._details = state, message, details
        self._sink.emit("plot_state", self.status())

    def _expect(self, *states: str) -> None:
        if self._state not in states:
            raise UserProblem(NOT_NOW)

    def _need_prepared(self) -> None:
        if self._state not in ("ready", "done") or self._prepared is None:
            raise UserProblem(PREPARE_FIRST if self._state in _AT_REST else FINISH_FIRST)

    def _warnings(self, clipped: bool, colors: int) -> list[str]:
        warnings = []
        for piece in list(self._session.pieces):
            for issue in piece.artwork.issues:
                if issue.code == "white" and not self._session.skip_white:
                    continue  # the student chose to draw white shapes after all
                if issue.message not in warnings:
                    warnings.append(issue.message)
        if clipped:
            warnings.append(CLIPPED)
        if colors >= MANY_COLORS:
            warnings.append(f"This drawing uses {colors} pen colors, so you'll change pens {colors - 1} times.")
        return warnings

    def _ask_for_pen(self) -> None:
        layer = self._prepared.layers[self._index]
        count = len(self._prepared.layers)
        self._set(
            "load_pen",
            f"Put the {layer.name} pen in the holder ({self._index + 1} of {count}), then click Continue.",
        )

    def _run_layer(self, resume: bool) -> None:
        layer = self._prepared.layers[self._index]
        svg = self._resume_svg if resume else self._prepared.svg
        settings, runner = self._settings, self._runner
        self._retry_resume = resume
        self._begin_run()
        self._set("plotting", f"Plotting the {layer.name} pen ({self._index + 1} of {len(self._prepared.layers)}).")
        self._start_worker(
            lambda: runner.run(svg, layer.number, settings, on_progress=self._on_progress, resume=resume),
            self._after_run,
        )

    def _begin_run(self) -> None:
        self._was_at_home, self._at_home = self._at_home, False
        self._pause_wanted = False

    def _start_worker(self, work, then) -> None:
        def target():
            try:
                result = work()
            except Exception as error:  # PlotRunner reports problems as results; this would be a bug
                logger.exception("The plot worker failed")
                result = PlotResult(PlotOutcome.ERROR, None, UNEXPECTED, details=f"{type(error).__name__}: {error}")
            with self._lock:
                try:
                    then(result)
                except Exception:
                    logger.exception("Couldn't finish handling the plot run")
                    self._set("ready", UNEXPECTED)

        self._worker = threading.Thread(target=target, name="rosetta-plot", daemon=True)
        self._worker.start()

    def _after_run(self, result: PlotResult) -> None:
        if result.resume_svg is not None:
            self._resume_svg = result.resume_svg
        outcome = result.outcome
        if outcome is PlotOutcome.COMPLETED:
            self._resume_svg = None
            self._at_home = True  # every layer run ends at Home
            self._index += 1
            if self._index < len(self._prepared.layers):
                self._ask_for_pen()
            else:
                self._index = 0
                self._machine.after_plot(at_home=True)
                self._set("done", DONE)
        elif outcome is PlotOutcome.PAUSED:
            self._set("paused", "Paused. The pen is up.")
        elif outcome is PlotOutcome.NOT_CONNECTED:
            self._at_home = self._was_at_home  # the run never started, so nothing moved
            self._set("not_connected", result.message)
        else:  # DISCONNECTED or ERROR
            self._lost(result)

    def _lost(self, result: PlotResult) -> None:
        """A pulled cable or an engine error: the pen may be anywhere (plan2-notes.md). With progress to
        come back to, ask for the cable and then a slide Home before resuming; otherwise end the plot."""
        if self._resume_svg is None:
            self._end_plot(result.message, result.details)
            return
        if result.outcome is PlotOutcome.DISCONNECTED:
            message = "Plotter disconnected. Plug it back in, then click Continue."
        else:
            message = f"{result.message} Check the USB cable and the power adapter, then click Continue."
        self._set("reconnect", message, result.details)

    def _end_plot(self, message: str, details: str = "") -> None:
        """Give the plotter back and drop the plot's progress. The prepared plot stays for a new start."""
        at_home = self._at_home
        self._resume_svg = None
        self._index = 0
        self._machine.after_plot(at_home=at_home)
        if not at_home:
            message = f"{message} {HOME_UNKNOWN}"
        self._set("ready", message, details)

    def _on_progress(self, progress) -> None:
        """Called on the engine's poller thread every 100 ms: never blocks, never takes the lock."""
        if self._pause_wanted:
            self._runner.pause()  # a pause asked for before this run's pause event existed
        prepared, index = self._prepared, self._index
        if prepared is None or index >= len(prepared.layers):
            return
        layer = prepared.layers[index]
        fraction = min(1.0, progress.pendown_mm / layer.pendown_mm) if layer.pendown_mm > 0 else 1.0
        later = sum(other.seconds for other in prepared.layers[index + 1:])
        self._sink.emit("plot_progress", {
            "layer": index,
            "x": round(progress.x_mm, 2),
            "y": round(progress.y_mm, 2),
            "pendown_mm": round(progress.pendown_mm, 1),
            "fraction": round(fraction, 4),
            "seconds_left": round(layer.seconds * (1 - fraction) + later, 1),
        })
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_plotjob.py -v`
Expected: `10 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\app\plotjob.py tests\test_plotjob.py
git commit -m "feat: PlotController prepares, traces and plots pen by pen" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: `PlotController`, part 2: pause, Return Home, resume, cancel, lost cable

Spec §10:
- **Paused** (from the app or the physical button): offers Resume, Return Home and Cancel plot.
- **USB lost:** "plug it back in, slide the pen Home, then click Resume." The resume then travels out from Home.

**Files:**
- Modify: `src/rosetta/app/plotjob.py`
- Test: `tests/test_plotjob.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plotjob.py`:
```python
from rosetta.app.plotjob import FINISH_FIRST, HOME_UNKNOWN, NOT_NOW
from rosetta.engine.runner import Progress


def _pause_after(rig, moves):
    """Press the app's Pause button once the plot has made this many moves."""
    rig.run_ebb.on_sm = lambda count: count == moves and rig.controller.pause()


def test_pause_then_resume_finishes_the_plot(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    _pause_after(rig, 5)
    rig.controller.start()
    rig.wait_until("paused")
    assert rig.controller.status()["actions"] == ["resume", "home", "cancel"]
    with pytest.raises(UserProblem, match=FINISH_FIRST):
        rig.controller.prepare()
    rig.controller.resume()
    rig.wait_until("done")


def test_return_home_while_paused(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    _pause_after(rig, 5)
    rig.controller.start()
    rig.wait_until("paused")
    rig.controller.home()
    rig.wait_until("paused_at_home")
    rig.controller.resume()
    rig.wait_until("done")


def test_cancel_while_paused_asks_for_a_new_home(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    _pause_after(rig, 5)
    rig.controller.start()
    rig.wait_until("paused")
    rig.controller.cancel()
    assert rig.state() == "ready" and HOME_UNKNOWN in rig.controller.status()["message"]
    assert rig.machine.status()["state"] == "not_homed"


def test_cancel_at_a_pen_change_keeps_home(tmp_path):
    rig = Rig(tmp_path, TWO_COLORS)
    rig.controller.prepare()
    rig.controller.start()
    rig.controller.cancel()
    assert rig.state() == "ready" and rig.machine.status()["state"] == "ready"


def test_a_pulled_cable_resumes_after_a_slide_home(tmp_path):
    rig = Rig(tmp_path, run_ebb=FakeEBB(die_after_moves=5, move_sleep=0))
    rig.controller.prepare()
    rig.controller.start()
    rig.wait_until("reconnect")
    assert "Plotter disconnected" in rig.controller.status()["message"]
    rig.run_ebb = FakeEBB(move_sleep=0)  # plugged back in
    rig.controller.reconnect()
    assert rig.state() == "slide_home"
    rig.controller.rehomed()
    assert rig.state() == "paused_at_home"
    rig.controller.resume()
    rig.wait_until("done")


def test_reconnect_waits_until_the_plotter_is_back(tmp_path):
    rig = Rig(tmp_path, run_ebb=FakeEBB(die_after_moves=5, move_sleep=0))
    rig.controller.prepare()
    rig.controller.start()
    rig.wait_until("reconnect")
    rig.bench.ebb = None  # still unplugged
    rig.controller.reconnect()
    assert rig.state() == "reconnect" and "Still no plotter" in rig.controller.status()["message"]


def test_retry_after_no_plotter_was_found(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    rig.run_ebb = None
    rig.controller.start()
    rig.wait_until("not_connected")
    rig.run_ebb = FakeEBB(move_sleep=0)
    rig.controller.retry()
    rig.wait_until("done")


def test_a_pause_asked_for_before_the_run_listens_is_asked_again(tmp_path):
    class CountingRunner:
        pauses = 0

        def pause(self):
            self.pauses += 1

    rig = Rig(tmp_path)
    runner = CountingRunner()
    controller = PlotController(rig.machine, rig.session, RecordingSink(), runner_factory=lambda: runner)
    controller.prepare()
    controller._pause_wanted = True  # what pause() leaves when the run wasn't listening yet
    controller._on_progress(Progress(1.0, 2.0, 3.0))
    assert runner.pauses == 1


def test_buttons_that_do_not_fit_the_state_are_refused(tmp_path):
    rig = Rig(tmp_path)
    rig.controller.prepare()
    for action in (rig.controller.resume, rig.controller.home, rig.controller.cancel,
                   rig.controller.continue_pen, rig.controller.reconnect, rig.controller.rehomed,
                   rig.controller.retry):
        with pytest.raises(UserProblem, match=NOT_NOW):
            action()
    rig.controller.pause()  # a late Pause click is harmless
    assert rig.state() == "ready"
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `.venv\Scripts\python -m pytest tests\test_plotjob.py -v`
Expected: the new tests fail with `AttributeError: 'PlotController' object has no attribute 'pause'` (and `resume`, `home`...).

- [ ] **Step 3: Add the methods**

In `src/rosetta/app/plotjob.py`, add `set_resume_origin_home` to the runner import:
```python
from rosetta.engine.runner import PlotOutcome, PlotResult, PlotRunner, set_resume_origin_home
```
and add these methods to `PlotController`, right after `continue_pen`:
```python
    def pause(self) -> None:
        """Pause at the next step, pen up. A late click after the run has ended does nothing."""
        with self._lock:
            if self._state not in ("plotting", "homing"):
                return
            self._pause_wanted = True
            self._runner.pause()
            if self._state == "plotting":
                self._set("pausing", "Pausing...")

    def resume(self) -> None:
        with self._lock:
            self._expect("paused", "paused_at_home")
            self._run_layer(resume=True)

    def home(self) -> None:
        """While paused: send the pen Home (to check or swap it). Resume then carries on from there."""
        with self._lock:
            self._expect("paused")
            svg, settings, runner = self._resume_svg, self._settings, self._runner
            self._begin_run()
            self._set("homing", "Sending the pen Home.")
            self._start_worker(lambda: runner.return_home(svg, settings), self._after_home)

    def cancel(self) -> None:
        """Stop the plot for good. If the pen isn't known to be Home, the motors go off for re-homing."""
        with self._lock:
            self._expect("load_pen", "paused", "paused_at_home", "reconnect", "slide_home", "not_connected")
            self._end_plot("Plot cancelled.")

    def reconnect(self) -> None:
        """After a lost cable or an error: once the plotter answers, free its carriage for a slide Home."""
        with self._lock:
            self._expect("reconnect")
            if self._machine.release_motors():
                self._set("slide_home", SLIDE_HOME)
            else:
                self._set("reconnect", "Still no plotter found. Check the USB cable and the power adapter, "
                                       "then click Continue.")

    def rehomed(self) -> None:
        """The student slid the pen Home, so the paused plot resumes from there (spec §10)."""
        with self._lock:
            self._expect("slide_home")
            self._resume_svg = set_resume_origin_home(self._resume_svg)
            self._at_home = True
            self._set("paused_at_home", "The pen is Home. Click Resume to carry on.")

    def retry(self) -> None:
        """Try the run again after it couldn't find the plotter (nothing moved)."""
        with self._lock:
            self._expect("not_connected")
            self._run_layer(resume=self._retry_resume)
```
and add this next to `_after_run`:
```python
    def _after_home(self, result: PlotResult) -> None:
        if result.resume_svg is not None:
            self._resume_svg = result.resume_svg
        outcome = result.outcome
        if outcome is PlotOutcome.COMPLETED:
            self._at_home = True
            self._set("paused_at_home", "The pen is Home. Check or swap it, then click Resume.")
        elif outcome is PlotOutcome.PAUSED:
            self._set("paused", result.message)
        elif outcome is PlotOutcome.NOT_CONNECTED:
            self._at_home = self._was_at_home
            self._set("paused", result.message)
        else:
            self._lost(result)
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_plotjob.py -v`
Expected: `19 passed`.
Run: `.venv\Scripts\python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\app\plotjob.py tests\test_plotjob.py
git commit -m "feat: pause, Return Home, resume, cancel and lost-cable recovery for plots" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: The bridge API (`Api`)

**Files:**
- Create: `src/rosetta/app/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

`tests/test_api.py`:
```python
import json
from types import SimpleNamespace

import pytest

from rosetta.app.api import UNEXPECTED, Api
from rosetta.app.events import RecordingSink
from rosetta.app.settings import SettingsStore
from rosetta.engine.runner import PlotRunner
from tests.app_helpers import make_machine, wait_for
from tests.fake_ebb import FakeEBB, IFakeEBB, fake_factory, skip_engine_waits

DRAWING = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">
<path d="M10 10 H90 V50 H10 Z" stroke="#000000" fill="none"/>
<path d="M20 30 H80" stroke="#ff0000" fill="none"/>
</svg>"""


@pytest.fixture(autouse=True)
def fast_engine(monkeypatch):
    skip_engine_waits(monkeypatch)


def make_api(tmp_path, ebb=None):
    machine, bench, store = make_machine(tmp_path, ebb)
    sink = RecordingSink()
    runner = PlotRunner(factory=fake_factory(FakeEBB(move_sleep=0)), poll_interval=0.001)
    return Api(store, sink, machine=machine, runner_factory=lambda: runner), sink


def ok(reply: dict) -> dict:
    assert reply["ok"], reply
    json.dumps(reply)  # everything has to cross the bridge as JSON
    return reply


def _drawing(tmp_path) -> str:
    path = tmp_path / "art.svg"
    path.write_text(DRAWING, encoding="utf-8")
    return str(path)


def _plotter():
    return IFakeEBB(nickname="Lab m1p1", move_sleep=0)


def test_the_page_sees_only_bridge_methods(tmp_path):
    api, _sink = make_api(tmp_path)
    public = [name for name in dir(api) if not name.startswith("_")]
    assert public and all(callable(getattr(api, name)) for name in public)
    assert all(hasattr(getattr(Api, name), "__wrapped__") for name in public)  # each replies {"ok": ...}


def test_app_start_describes_everything(tmp_path):
    reply = ok(make_api(tmp_path)[0].app_start())
    assert reply["settings"]["units"] == "in"
    assert (len(reply["papers"]), len(reply["models"]), len(reply["pen_types"])) == (7, 7, 3)
    assert reply["machine"]["state"] == "no_plotter" and reply["plot"]["state"] == "idle"
    assert reply["material"]["width"] == pytest.approx(279.4)


def test_problems_come_back_in_plain_language(tmp_path):
    reply = make_api(tmp_path)[0].artwork_import(str(tmp_path / "drawing.afdesign"))
    assert not reply["ok"] and "In Affinity, use File › Export" in reply["message"]


def test_unexpected_errors_are_logged_and_explained(tmp_path, monkeypatch, caplog):
    api, _sink = make_api(tmp_path)
    monkeypatch.setattr(api._session, "add", lambda *args: 1 / 0)
    reply = api.artwork_import("x.svg")
    assert reply == {"ok": False, "message": UNEXPECTED, "details": "ZeroDivisionError: division by zero"}
    assert "artwork_import failed" in caplog.text


def test_settings_are_remembered(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.set_units("mm"))
    ok(api.material_set("a4", "portrait"))
    refused = api.set_advanced({"accel": 500})
    assert not refused["ok"] and refused["message"] == "Acceleration must be from 1 to 100."
    ok(api.set_advanced({"accel": 60}))
    saved = SettingsStore(tmp_path / "settings.json").settings
    assert (saved.units, saved.paper.size, saved.paper.orientation, saved.advanced.accel) == ("mm", "a4", "portrait", 60)


def test_a_custom_paper_must_be_a_real_size(tmp_path):
    reply = make_api(tmp_path)[0].material_set("custom", "landscape", 0, 100)
    assert not reply["ok"] and "between 0 and 2000 mm" in reply["message"]


def test_import_arrange_and_list_pens(tmp_path):
    api, _sink = make_api(tmp_path)
    reply = ok(api.artwork_import(_drawing(tmp_path)))
    assert reply["piece"]["id"] == "piece-1" and not reply["shrunk"]
    placed = ok(api.piece_place("piece-1", 10, 20, 0.5, 90))["placement"]
    assert placed == {"x": 10.0, "y": 20.0, "scale": 0.5, "rotation": 90}
    assert ok(api.piece_duplicate("piece-1"))["piece"]["id"] == "piece-2"
    ok(api.piece_delete("piece-1"))
    assert [color["name"] for color in ok(api.job_colors())["colors"]] == ["black", "red"]
    assert ok(api.artwork_pages(_drawing(tmp_path)))["pages"] == 1


def test_a_whole_plot_through_the_bridge(tmp_path):
    api, sink = make_api(tmp_path, _plotter())
    assert ok(api.plotter_scan())["machine"]["state"] == "not_homed"
    assert ok(api.plotter_set_home())["machine"]["state"] == "ready"
    assert ok(api.plotter_jog(10, 5))["machine"]["position"] == pytest.approx([10, 5])
    ok(api.material_set("letter", "landscape"))
    ok(api.artwork_import(_drawing(tmp_path)))
    summary = ok(api.plot_prepare())["summary"]
    assert [layer["name"] for layer in summary["layers"]] == ["black", "red"]
    assert ok(api.plot_start())["plot"]["state"] == "load_pen"
    ok(api.plot_continue())
    wait_for(lambda: api.plot_status()["plot"]["state"] == "load_pen" and api.plot_status()["plot"]["layer"] == 1)
    ok(api.plot_continue())
    wait_for(lambda: api.plot_status()["plot"]["state"] == "done")
    assert sink.named("plot_progress")


def test_pen_settings_are_remembered_per_plotter(tmp_path):
    ebb = _plotter()
    api, _sink = make_api(tmp_path, ebb)
    ok(api.plotter_scan())
    ok(api.pen_set(45, "marker"))
    again, _sink = make_api(tmp_path, ebb)
    machine = ok(again.plotter_scan())["machine"]
    assert (machine["pen_down"], machine["pen_type"]) == (45, "marker")


def test_mark_this_corner_uses_the_pen_position(tmp_path):
    api, _sink = make_api(tmp_path, _plotter())
    ok(api.plotter_scan())
    assert not api.material_mark_corner()["ok"]  # not homed yet
    ok(api.plotter_set_home())
    ok(api.plotter_goto(25, 15))
    material = ok(api.material_mark_corner())["material"]
    assert (material["x"], material["y"]) == pytest.approx((25, 15))


def test_closing_when_nothing_is_plotting(tmp_path):
    api, _sink = make_api(tmp_path, _plotter())
    ok(api.plotter_scan())
    assert api._on_closing() is True
    assert api.plotter_scan()["machine"]["state"] == "not_homed"  # shut down, then found again


def test_closing_mid_plot_asks_the_page_first(tmp_path):
    api, sink = make_api(tmp_path, _plotter())
    ok(api.plotter_scan())
    ok(api.plotter_set_home())
    ok(api.artwork_import(_drawing(tmp_path)))
    ok(api.plot_prepare())
    ok(api.plot_start())  # waiting for the first pen
    assert api._on_closing() is False
    assert sink.named("close_requested") == [{}]
    destroyed = []
    api._attach_window(SimpleNamespace(destroy=lambda: destroyed.append(True)), choose_files=None)
    ok(api.quit_confirmed())
    assert destroyed and api._on_closing() is True


def test_dropped_files_reach_the_page(tmp_path):
    api, sink = make_api(tmp_path)
    api._files_dropped(["C:\\art.svg"])
    assert sink.named("files_dropped") == [{"paths": ["C:\\art.svg"]}]


def test_the_file_picker(tmp_path):
    api, _sink = make_api(tmp_path)
    assert not api.artwork_choose()["ok"]
    api._attach_window(None, choose_files=lambda: ("C:\\a.svg", "C:\\b.pdf"))
    assert ok(api.artwork_choose())["paths"] == ["C:\\a.svg", "C:\\b.pdf"]
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python -m pytest tests\test_api.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'rosetta.app.api'`.

- [ ] **Step 3: Write `src/rosetta/app/api.py`**

```python
"""The page's way into Python (spec §6.5), documented in docs/bridge.md.

Every public method can be called from the page as `await window.pywebview.api.<name>(...)`. pywebview
runs each call on its own thread, so a slow one (an import, a plan, a move) never freezes the window.
Each replies {"ok": true, ...} or {"ok": false, "message": ..., "details": ...}.
pywebview exposes every public attribute it finds, so everything else here starts with an underscore.
"""
import dataclasses
import functools
import logging
import math

import rosetta
from rosetta.app import payloads
from rosetta.app.logs import diagnostics as diagnostics_text
from rosetta.app.machine import NOT_HOMED, Machine, MachineState
from rosetta.app.paper import CUSTOM, PAPER_SIZES, paper_dimensions
from rosetta.app.plotjob import FINISH_FIRST, PlotController
from rosetta.app.session import Session, pages_in
from rosetta.app.settings import MAX_MARGIN_MM, UNITS, PaperChoice, PenProfile, SettingsStore
from rosetta.compose import Material
from rosetta.engine.options import (
    ADVANCED_CHOICES, ADVANCED_LABELS, ADVANCED_RANGES, MIN_PEN_TRAVEL, PEN_DOWN_MAX, advanced_from_dict,
)
from rosetta.errors import ImportProblem, UserProblem
from rosetta.models import MODELS, PEN_TYPES, get_model

logger = logging.getLogger(__name__)

UNEXPECTED = "Something unexpected went wrong. Click Details, or Copy diagnostics to ask for help."
ARTWORK_TYPES = ("Drawings (*.svg;*.pdf;*.ai)",)
LARGEST_MODEL = 5  # SE/A1: before a plotter is known, only the paper limits the Pens panel
MAX_LABEL = 40


def _bridge(method):
    """Turn a method's result, or its exception, into the reply the page expects."""

    @functools.wraps(method)
    def call(self, *args):
        try:
            result = method(self, *args)
        except (UserProblem, ImportProblem) as problem:
            return {"ok": False, "message": str(problem), "details": getattr(problem, "details", "")}
        except Exception as error:  # a bug, or the plotter doing something odd: log it, say it plainly
            logger.exception("%s failed", method.__name__)
            return {"ok": False, "message": UNEXPECTED, "details": f"{type(error).__name__}: {error}"}
        return {"ok": True, **(result or {})}

    return call


def _finite(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Expected a number, got {value!r}")
    return float(value)


class Api:
    def __init__(self, store: SettingsStore, sink, machine: Machine | None = None,
                 runner_factory=None, log_path=None):
        self._store = store
        self._sink = sink
        self._machine = machine or Machine(store)
        self._machine.advanced = store.settings.advanced
        self._session = Session(self._saved_material(), store.settings.margin_mm)
        extra = {} if runner_factory is None else {"runner_factory": runner_factory}
        self._plot = PlotController(self._machine, self._session, sink, **extra)
        self._log_path = log_path
        self._window = None
        self._choose_files = None
        self._closing_allowed = False
        self._profile_key = None

    # Wiring for main.py (underscored, so the page can't call it).

    def _attach_window(self, window, choose_files) -> None:
        self._window = window
        self._choose_files = choose_files

    def _files_dropped(self, paths: list[str]) -> None:
        self._sink.emit("files_dropped", {"paths": list(paths)})

    def _on_closing(self) -> bool:
        """The window's closing event; True lets it close. Mid-plot the page is asked to confirm first
        (spec §10), and its Quit button calls quit_confirmed()."""
        if self._closing_allowed or not self._plot.busy():
            self._plot.shutdown()
            self._machine.shutdown()
            return True
        self._sink.emit("close_requested", {})
        return False

    # App.

    @_bridge
    def app_start(self):
        """Everything the page needs for its first screen."""
        settings = self._store.settings
        return {
            "version": rosetta.__version__,
            "settings": {
                "units": settings.units,
                "margin_mm": settings.margin_mm,
                "paper": dataclasses.asdict(settings.paper),
                "advanced": dataclasses.asdict(settings.advanced),
            },
            "models": [
                {"number": model.number, "name": model.name, "travel": list(model.travel_mm)}
                for model in MODELS.values()
            ],
            "pen_types": [
                {"key": pen.key, "label": pen.label, "speed": pen.speed_pendown} for pen in PEN_TYPES.values()
            ],
            "papers": [
                {"key": paper.key, "label": paper.label, "short_mm": paper.short_mm, "long_mm": paper.long_mm}
                for paper in PAPER_SIZES.values()
            ],
            "advanced_options": {
                "labels": ADVANCED_LABELS,
                "ranges": {name: list(bounds) for name, bounds in ADVANCED_RANGES.items()},
                "choices": {name: list(values) for name, values in ADVANCED_CHOICES.items()},
            },
            "pen_down_max": PEN_DOWN_MAX,
            "machine": self._machine.status(),
            "material": self._material(),
            "plot": self._plot.status(),
        }

    @_bridge
    def set_units(self, units):
        if units not in UNITS:
            raise ValueError(f"Unknown units: {units!r}")
        self._store.settings.units = units
        self._store.save()

    @_bridge
    def set_advanced(self, values):
        try:
            advanced = advanced_from_dict(dict(values))
        except (ValueError, TypeError) as problem:  # typed by the student, so the message is for them
            raise UserProblem(str(problem)) from problem
        pen_down = self._machine.pen_down
        if advanced.pen_up is not None and advanced.pen_up - pen_down < MIN_PEN_TRAVEL:
            raise UserProblem(
                f"Pen-up height must be at least {MIN_PEN_TRAVEL} above the pen-down height ({pen_down})."
            )
        self._machine.advanced = advanced
        self._store.settings.advanced = advanced
        self._store.save()
        self._plot.invalidate()
        return {"advanced": dataclasses.asdict(advanced)}

    @_bridge
    def diagnostics(self):
        machine = self._machine.status()
        extra = {
            "Plotter": f"{machine['model_name'] or 'unknown model'} ({machine['state']}), "
                       f"firmware {machine['firmware'] or 'unknown'}",
            "Plot": self._plot.status()["state"],
        }
        return {"text": diagnostics_text(self._log_path, extra)}

    @_bridge
    def quit_confirmed(self):
        """The student confirmed closing mid-plot: the closing event then pauses it and lifts the pen."""
        self._closing_allowed = True
        if self._window is not None:
            self._window.destroy()

    # Step 1 and Re-home: the plotter.

    @_bridge
    def plotter_scan(self):
        """Look for the plotter (the page calls this every 2 s while none is connected)."""
        self._machine.scan()
        self._load_profile()
        return {"machine": self._machine.status()}

    @_bridge
    def plotter_identify(self, model, penlift, label=""):
        if model not in MODELS or penlift not in (1, 2, 3) or not isinstance(label, str) or len(label) > MAX_LABEL:
            raise ValueError(f"Bad plotter identity: {model!r}, {penlift!r}, {label!r}")
        self._machine.identify(model, penlift, label)
        self._load_profile()
        return {"machine": self._machine.status()}

    @_bridge
    def plotter_motors_off(self):
        return {"machine": self._machine.motors_off()}

    @_bridge
    def plotter_set_home(self):
        return {"machine": self._machine.set_home()}

    @_bridge
    def plotter_jog(self, dx, dy):
        return {"machine": self._machine.jog(_finite(dx), _finite(dy))}

    @_bridge
    def plotter_goto(self, x, y):
        return {"machine": self._machine.goto(_finite(x), _finite(y))}

    @_bridge
    def plotter_pen(self, down):
        return {"machine": self._machine.pen(bool(down))}

    @_bridge
    def plotter_stop(self):
        self._machine.request_stop()

    @_bridge
    def plotter_test_mark(self):
        material = self._session.material
        return {"machine": self._machine.test_mark(material.x, material.y)}

    @_bridge
    def pen_set(self, pen_down, pen_type):
        status = self._machine.set_pen(pen_down, pen_type)
        key = self._machine.profile_key()
        if key:
            self._store.settings.profiles[key] = PenProfile(pen_down, pen_type)
            self._store.save()
        self._plot.invalidate()
        return {"machine": status}

    # Step 2: the paper.

    @_bridge
    def material_set(self, size, orientation, custom_width_mm=None, custom_height_mm=None, x=0.0, y=0.0):
        width, height = paper_dimensions(size, orientation, custom_width_mm, custom_height_mm)
        x, y = _finite(x), _finite(y)
        if x < 0 or y < 0:
            raise UserProblem("Place the paper's corner at the Home corner or farther from it.")
        self._session.material = Material(x, y, width, height)
        custom = size == CUSTOM
        self._store.settings.paper = PaperChoice(
            size, orientation, width if custom else None, height if custom else None
        )
        self._store.save()
        self._plot.invalidate()
        return {"material": self._material()}

    @_bridge
    def material_mark_corner(self):
        """"Mark this corner": the paper's corner nearest Home is where the pen is now (spec §5, step 2)."""
        if self._machine.state is not MachineState.READY:
            raise UserProblem(NOT_HOMED)
        x, y = self._machine.position
        self._session.material = dataclasses.replace(self._session.material, x=x, y=y)
        self._plot.invalidate()
        return {"material": self._material()}

    @_bridge
    def set_margin(self, margin_mm):
        margin = _finite(margin_mm)
        if not 0 <= margin <= MAX_MARGIN_MM:
            raise UserProblem(f"The margin must be from 0 to {MAX_MARGIN_MM:g} mm.")
        self._session.margin_mm = margin
        self._store.settings.margin_mm = margin
        self._store.save()
        return {"margin_mm": margin}

    # Step 3: artwork.

    @_bridge
    def artwork_choose(self):
        """Windows' Open dialog. The page then asks for page counts and imports each chosen file."""
        if self._choose_files is None:
            raise UserProblem("The file picker isn't available.")
        return {"paths": [str(path) for path in (self._choose_files() or [])]}

    @_bridge
    def artwork_pages(self, path):
        return {"pages": pages_in(path)}

    @_bridge
    def artwork_import(self, path, page=0):
        piece, shrunk = self._session.add(path, int(page))
        self._plot.invalidate()
        return {"piece": payloads.piece_payload(piece), "shrunk": shrunk}

    @_bridge
    def piece_place(self, piece_id, x, y, scale, rotation):
        piece = self._session.place(piece_id, x, y, scale, rotation)
        self._plot.invalidate()
        return {"placement": payloads.placement_payload(piece.placement)}

    @_bridge
    def piece_duplicate(self, piece_id):
        piece = self._session.duplicate(piece_id)
        self._plot.invalidate()
        return {"piece": payloads.piece_payload(piece)}

    @_bridge
    def piece_delete(self, piece_id):
        self._session.remove(piece_id)
        self._plot.invalidate()

    @_bridge
    def set_skip_white(self, skip):
        self._session.skip_white = bool(skip)
        self._plot.invalidate()
        return {"skip_white": self._session.skip_white}

    @_bridge
    def job_colors(self):
        """The pens the drawing needs, in plot order (the Pens panel)."""
        identity = self._machine.identity
        model = get_model(identity.model if identity else LARGEST_MODEL)
        return payloads.job_payload(self._session.compose(model))

    @_bridge
    def new_plot(self):
        """Start again with empty paper (the Done screen's New plot)."""
        if self._plot.busy():
            raise UserProblem(FINISH_FIRST)
        self._session.clear()
        self._plot.invalidate()

    # Step 5: the plot.

    @_bridge
    def plot_prepare(self):
        return {"summary": self._plot.prepare()}

    @_bridge
    def plot_trace(self):
        return {"machine": self._plot.trace()}

    @_bridge
    def plot_start(self):
        self._plot.start()
        return self._plot_reply()

    @_bridge
    def plot_continue(self):
        self._plot.continue_pen()
        return self._plot_reply()

    @_bridge
    def plot_pause(self):
        self._plot.pause()
        return self._plot_reply()

    @_bridge
    def plot_resume(self):
        self._plot.resume()
        return self._plot_reply()

    @_bridge
    def plot_home(self):
        self._plot.home()
        return self._plot_reply()

    @_bridge
    def plot_cancel(self):
        self._plot.cancel()
        return self._plot_reply()

    @_bridge
    def plot_reconnect(self):
        self._plot.reconnect()
        return self._plot_reply()

    @_bridge
    def plot_rehomed(self):
        self._plot.rehomed()
        return self._plot_reply()

    @_bridge
    def plot_retry(self):
        self._plot.retry()
        return self._plot_reply()

    @_bridge
    def plot_status(self):
        return self._plot_reply()

    # Inside.

    def _plot_reply(self) -> dict:
        return {"plot": self._plot.status(), "machine": self._machine.status()}

    def _material(self) -> dict:
        identity = self._machine.identity
        return payloads.material_payload(self._session.material, get_model(identity.model) if identity else None)

    def _saved_material(self) -> Material:
        paper = self._store.settings.paper
        try:
            width, height = paper_dimensions(
                paper.size, paper.orientation, paper.custom_width_mm, paper.custom_height_mm
            )
        except (UserProblem, ValueError):
            width, height = paper_dimensions("letter", "landscape")
        return Material(0.0, 0.0, width, height)

    def _load_profile(self) -> None:
        """When a different plotter shows up, start from the pen settings it was last used with."""
        key = self._machine.profile_key()
        if key == self._profile_key:
            return
        self._profile_key = key
        profile = self._store.settings.profiles.get(key) if key else None
        if profile is not None:
            try:
                self._machine.set_pen(profile.pen_down, profile.pen_type)
            except (UserProblem, ValueError):
                logger.info("Couldn't use the saved pen settings for %s", key, exc_info=True)
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_api.py -v`
Expected: `14 passed`.
Run: `.venv\Scripts\python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\app\api.py tests\test_api.py
git commit -m "feat: the pywebview bridge API the student page calls" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: The window, the bridge console, and `docs/bridge.md`

The window:
- shows Plan 2b's built page from `ui/dist/index.html`;
- shows Vite's dev server instead when `ROSETTA_UI_URL` is set;
- shows a small "bridge console" until the page is built, so every method can be tried by hand.

Dropped files:
- reach Python with full paths, through pywebview's DOM drop events, because the page itself only sees file names;
- go back to the page as `files_dropped`.

**Files:**
- Create: `src/rosetta/app/main.py`, `src/rosetta/app/console.html`, `scripts/smoke_window.py`, `docs/bridge.md`
- Modify: `README.md`
- Test: `tests/test_app_main.py`

- [ ] **Step 1: Write the failing test**

`tests/test_app_main.py`:
```python
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
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `.venv\Scripts\python -m pytest tests\test_app_main.py -v`
Expected: collection error, `ImportError: cannot import name 'main' from 'rosetta.app'`.

- [ ] **Step 3: Write `src/rosetta/app/main.py`**

```python
"""Start Rosetta Plotter: one WebView2 window (spec §6.5) showing the student page, with Api as its bridge.

Run `.venv\\Scripts\\rosetta-app` (no console window), or `.venv\\Scripts\\python -m rosetta.app.main`
to see Python's output while developing. Set ROSETTA_UI_URL=http://localhost:5173 to show Vite's dev
server instead of ui/dist, and ROSETTA_DEBUG=1 to allow WebView2's developer tools.
"""
import logging
import os
import sys
from pathlib import Path

import webview
from webview.dom import DOMEventHandler

from rosetta.app.api import ARTWORK_TYPES, Api
from rosetta.app.events import WindowSink
from rosetta.app.logs import setup_logging, stop_logging
from rosetta.app.settings import SettingsStore, app_folder
from rosetta.engine.options import ensure_std_streams

logger = logging.getLogger(__name__)

TITLE = "Rosetta Plotter"
START_SIZE = (1280, 800)
MIN_SIZE = (1024, 700)  # spec §6.5
BACKGROUND = "#e3e3e3"  # the canvas gray, shown while the page loads
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


def main() -> int:
    ensure_std_streams()
    log_path = setup_logging(app_folder() / "logs")
    logger.info("Rosetta Plotter starting")
    store = SettingsStore(app_folder() / "settings.json")
    sink = WindowSink()
    api = Api(store, sink, log_path=log_path)
    entry = ui_entry()
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
    try:
        webview.start(gui="edgechromium", http_server=True, debug=bool(os.environ.get(DEBUG_VARIABLE)))
    finally:
        sink.close()
        logger.info("Rosetta Plotter closed")
        stop_logging()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write `src/rosetta/app/console.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Rosetta Plotter: bridge console</title>
<style>
  body { font: 14px "Segoe UI", system-ui, sans-serif; margin: 16px; background: #f3f3f3; color: #1b1b1b; }
  h1 { font-size: 18px; margin: 0 0 4px; }
  h2 { font-size: 15px; margin: 12px 0 4px; }
  p { margin: 0 0 12px; color: #555; }
  .row { display: flex; gap: 8px; margin-bottom: 8px; }
  select, input, button { font: inherit; padding: 4px 8px; }
  input { flex: 1; font-family: Consolas, monospace; }
  pre { background: #fff; border: 1px solid #ccc; padding: 8px; height: 36vh; overflow: auto; margin: 0;
        white-space: pre-wrap; }
</style>
</head>
<body>
<h1>Rosetta Plotter: bridge console</h1>
<p>The student screens aren't built yet. Pick a bridge method, type its arguments as a JSON list, then click Call.</p>
<div class="row">
  <select id="method" aria-label="Bridge method"></select>
  <input id="args" value="[]" aria-label="Arguments as a JSON list">
  <button id="call">Call</button>
</div>
<pre id="reply">Waiting for the bridge...</pre>
<h2>Events</h2>
<pre id="events"></pre>
<script>
  const reply = document.getElementById("reply");
  const events = document.getElementById("events");
  window.rosettaEvent = (name, data) => {
    events.textContent = `${new Date().toLocaleTimeString()} ${name} ${JSON.stringify(data)}\n` + events.textContent;
  };
  window.addEventListener("pywebviewready", () => {
    const select = document.getElementById("method");
    for (const name of Object.keys(window.pywebview.api).sort()) {
      select.add(new Option(name, name));
    }
    reply.textContent = "Ready.";
    document.getElementById("call").addEventListener("click", async () => {
      let args;
      try {
        args = JSON.parse(document.getElementById("args").value || "[]");
        if (!Array.isArray(args)) throw new Error("Type the arguments as a JSON list, like [10, 5].");
      } catch (error) {
        reply.textContent = String(error);
        return;
      }
      reply.textContent = "...";
      try {
        reply.textContent = JSON.stringify(await window.pywebview.api[select.value](...args), null, 2);
      } catch (error) {
        reply.textContent = `Error: ${error.message || error}`;
      }
    });
  });
</script>
</body>
</html>
```

Hatch already packs every file inside `src/rosetta`, so the wheel carries `console.html` with no extra setting.

- [ ] **Step 5: Run the tests**

Run: `.venv\Scripts\python -m pytest tests\test_app_main.py -v`
Expected: `4 passed`.

- [ ] **Step 6: Write the window smoke test script and run it**

This one opens a real window, so it isn't part of pytest. It needs this machine's desktop session and WebView2. It checks the following, then closes the window:
- the page sees every bridge method;
- an event reaches the page.

`scripts/smoke_window.py`:
```python
"""Open the real Rosetta window for a moment and check the bridge works both ways, then close it.

Not part of pytest (it needs a desktop session and WebView2). Run:
    .venv\\Scripts\\python scripts\\smoke_window.py
"""
import sys
import tempfile
import time
from pathlib import Path

import webview

from rosetta.app.api import Api
from rosetta.app.events import WindowSink
from rosetta.app.main import console_html
from rosetta.app.settings import SettingsStore


def main() -> int:
    sink = WindowSink()
    api = Api(SettingsStore(Path(tempfile.mkdtemp()) / "settings.json"), sink)
    window = webview.create_window("Rosetta smoke test", html=console_html(), js_api=api)
    sink.attach(window.evaluate_js)
    seen = {}

    def check():
        try:
            seen["methods"] = window.evaluate_js("Object.keys(window.pywebview.api).length")
            sink.emit("smoke", {"hello": "page"})
            time.sleep(1)
            seen["events"] = window.evaluate_js("document.getElementById('events').textContent")
        finally:
            window.destroy()

    webview.start(check, gui="edgechromium", http_server=True)
    sink.close()
    expected = len([name for name in dir(api) if not name.startswith("_")])
    passed = seen.get("methods") == expected and "smoke" in (seen.get("events") or "")
    print(seen)
    print("PASS" if passed else f"FAIL (expected {expected} methods and a smoke event)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
```

Run: `.venv\Scripts\python scripts\smoke_window.py`
Expected: a window flashes up for about a second, then `{'methods': 39, 'events': '... smoke {"hello":"page"}\n'}` and `PASS`.
- If it says FAIL with `'methods': None`, the page never loaded. Rerun it with `$env:ROSETTA_DEBUG=1` and read the console output.
- The number of methods must match `dir(api)`. The script checks that itself, so 39 here is only a guide.

- [ ] **Step 7: Write `docs/bridge.md`**

````markdown
# Rosetta Plotter bridge (Python ↔ page)

The student page talks to Python through pywebview's `js_api`, the `Api` class in `src/rosetta/app/api.py`. Plan 2b's front end is built on exactly this contract. Change the two together.

## Calling Python

- Wait for the window's `pywebviewready` event, then call `await window.pywebview.api.<method>(...args)`. Arguments are positional.
- Each call runs on its own Python thread, so the slow ones don't freeze the window. Show a spinner while awaiting them. The slow ones are `artwork_import`, `plot_prepare`, moves, `plot_trace` and `plotter_identify`.
- Every reply is `{"ok": true, ...fields}` or `{"ok": false, "message": "...", "details": "..."}`.
  - Show `message` exactly as written. It's plain language for students.
  - Put `details` behind a **Details** link.
- **Units:** all lengths are millimetres in the machine frame.
  - (0, 0) is the Home corner. x runs along the rail, y toward the student.
  - The page converts to inches only for display.

## Methods

### App
| Method | Arguments | Reply |
|---|---|---|
| `app_start()` | | `version`, `settings` {units, margin_mm, paper, advanced}, `models` [{number, name, travel}], `pen_types` [{key, label, speed}], `papers` [{key, label, short_mm, long_mm}], `advanced_options` {labels, ranges, choices}, `pen_down_max`, `machine`, `material`, `plot` |
| `set_units(units)` | `"in"` or `"mm"` | |
| `set_advanced(values)` | {option: value}; `null` means automatic for `pen_up` and `speed_pendown` | `advanced` |
| `diagnostics()` | | `text` for Copy diagnostics |
| `quit_confirmed()` | | closes the window; a running plot is paused, pen up |

### Plotter (Step 1, Re-home, Steps 2 and 4)
| Method | Arguments | Reply |
|---|---|---|
| `plotter_scan()` | | `machine`. Call every 2 s while `machine.state` is `no_plotter` |
| `plotter_identify(model, penlift, label)` | model 1–7, penlift 1–3 (3 = brushless upgrade), label ≤ 40 characters | `machine`. `nickname` echoes what the plotter stored |
| `plotter_motors_off()` | | `machine` (`not_homed`: show the slide-Home instruction) |
| `plotter_set_home()` | | `machine` (`ready`, position [0, 0]) |
| `plotter_jog(dx, dy)` | mm | `machine` |
| `plotter_goto(x, y)` | mm from Home | `machine` |
| `plotter_pen(down)` | true or false | `machine` |
| `plotter_stop()` | | stops a move or trace in progress |
| `plotter_test_mark()` | | `machine` (a 10 mm line by the paper corner nearest Home, then Home) |
| `pen_set(pen_down, pen_type)` | 0–`pen_down_max`, a `pen_types` key | `machine`. Remembered for this plotter; a down pen moves at once |

### Material (Step 2)
| Method | Arguments | Reply |
|---|---|---|
| `material_set(size, orientation, custom_width_mm, custom_height_mm, x, y)` | `size` is a `papers` key or `"custom"`. `orientation` is `"landscape"` or `"portrait"`. Custom sizes are taken exactly as typed. `x`, `y` is the paper corner nearest Home | `material` |
| `material_mark_corner()` | | `material` with x, y = the pen's position (needs a homed plotter) |
| `set_margin(margin_mm)` | 0–50 | `margin_mm` |

### Artwork (Step 3)
| Method | Arguments | Reply |
|---|---|---|
| `artwork_choose()` | | `paths` (empty if cancelled) |
| `artwork_pages(path)` | | `pages`. Ask which page when it's more than 1 |
| `artwork_import(path, page)` | page counts from 0 | `piece`, `shrunk` (true: say it was scaled down to fit) |
| `piece_place(id, x, y, scale, rotation)` | rotation 0, 90, 180 or 270 | `placement` |
| `piece_duplicate(id)` | | `piece` (offset 10 mm) |
| `piece_delete(id)` | | |
| `set_skip_white(skip)` | | `skip_white` |
| `job_colors()` | | `colors` [{layer, color, name, lines}], `ink_bbox`, `clipped`, `empty` |
| `new_plot()` | | clears the paper (refused mid-plot) |

### Plot (Step 5)
| Method | Reply |
|---|---|
| `plot_prepare()` | `summary` (slow: plans every pen) |
| `plot_trace()` | `machine`. Returns when the trace ends; `plotter_stop()` ends it early |
| `plot_start()`, `plot_continue()`, `plot_pause()`, `plot_resume()`, `plot_home()`, `plot_cancel()`, `plot_reconnect()`, `plot_rehomed()`, `plot_retry()` | `plot`, `machine` |
| `plot_status()` | `plot`, `machine` |

The page shows one button per entry in `plot.actions`. Each action maps to a method:

| Action | Method |
|---|---|
| `trace` | `plot_trace` |
| `start` | `plot_start` ("Start", or "Plot another copy" when done) |
| `continue` | `plot_continue` |
| `pause` | `plot_pause` |
| `resume` | `plot_resume` |
| `home` | `plot_home` |
| `cancel` | `plot_cancel` |
| `reconnect` | `plot_reconnect` |
| `rehomed` | `plot_rehomed` ("It's in the corner") |
| `retry` | `plot_retry` |
| `stop` | `plotter_stop` |

## Shapes

- **machine**:
  - `state`: one of `no_plotter`, `needs_model`, `not_homed`, `ready`, `plotting`
  - also: `firmware`, `power_ok`, `model`, `model_name`, `penlift`, `label`, `nickname`, `old_firmware`, `pen_down`, `pen_type`
  - `position`: [x, y] only when `ready`, otherwise null
- **material**: `x`, `y`, `width`, `height`, `reach` [x, y] or null, `fits` (true, false, or null before a plotter is known)
- **piece**:
  - `id`, `name`, `path`, `page`, `width_mm`, `height_mm`, `placement` {x, y, scale, rotation}, `issues` [{code, message, count}]
  - `groups` [{color, name, white, lines}]. `lines` is a list of flat lists [x0, y0, x1, y1, …] in artwork mm, before placement.
  - `preview`: a `data:image/svg+xml;base64,…` URL to draw under the lines with an SVG `<image>`, or null.
- **Placement math:** the rotated, scaled artwork box's top-left sits at (x, y) from the paper's corner. Rotation turns clockwise on screen. See `rosetta.geometry.place_point`.
- **plot**: `state`, `actions`, `layer` (0-based), `layers`, `color`, `name`, `message`, `details`
- **summary**:
  - `layers` [{layer, color, name, seconds, pendown_mm, path}]
  - `path` is a list of runs [{down, points}], with `points` flattened as [x, y, t, x, y, t, …]. Here t is seconds from the start of that pen's run.
  - also: `total_seconds`, `ink_bbox`, `warnings`

## Events

Python calls `window.rosettaEvent(name, data)`:

| Event | Data |
|---|---|
| `plot_state` | the **plot** shape, on every change |
| `plot_progress` | `layer`, `x`, `y`, `pendown_mm`, `fraction`, `seconds_left`. About every 100 ms; only the newest is sent if the page falls behind |
| `files_dropped` | `paths`: call `artwork_pages` and `artwork_import` for each |
| `close_requested` | {}: the window was closed mid-plot. Ask "Stop the plot and close?", then call `quit_confirmed()` |

## Plot states

| State | Means |
|---|---|
| `idle` | nothing prepared |
| `ready` | prepared |
| `tracing` | pen-up outline in progress |
| `load_pen` | `message` says which pen to put in the holder |
| `plotting` | drawing |
| `pausing` | stopping at the next step |
| `paused` | pen up where it stopped |
| `homing` | returning Home while paused |
| `paused_at_home` | paused, pen Home |
| `reconnect` | cable lost or engine error: plug it back in |
| `slide_home` | slide the pen Home by hand |
| `not_connected` | a run found no plotter; nothing moved |
| `done` | finished, pen Home |
````

- [ ] **Step 8: Mention the app in `README.md`**

Add this to the end of the developer setup section of `README.md`:
```markdown
Run the app (until the student screens are built it shows a bridge console for trying every method):

    .venv\Scripts\python -m rosetta.app.main

The bridge between Python and the page is documented in docs/bridge.md.
```

- [ ] **Step 9: Run everything**

Run: `.venv\Scripts\python -m pytest -q`
Expected: all pass, about 640 tests in all (501 at the start).

- [ ] **Step 10: Commit**

```powershell
git add src\rosetta\app\main.py src\rosetta\app\console.html scripts\smoke_window.py docs\bridge.md README.md tests\test_app_main.py
git commit -m "feat: the Rosetta window, a bridge console, and the bridge contract for Plan 2b" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 11 (optional, needs Adam and the plotter): try the bridge on hardware**

With the plotter plugged in and powered:
1. Run `.venv\Scripts\python -m rosetta.app.main`.
2. In the console, call these in order:
   - `plotter_scan` → state `not_homed`, or `needs_model` until Task 21's `identify` has been run
   - `plotter_set_home` with the pen slid Home
   - `plotter_jog` `[20, 0]`. The pen moves 20 mm to the right, along the rail.
   - `plotter_goto` `[0, 0]`
   - `plotter_pen` `[true]`, then `[false]`
3. Drag an SVG onto the window. The Events box shows `files_dropped` with its full path.
4. Close the window. It closes at once, since nothing is plotting.

Note anything odd in `docs/hardware-log.md`.

---

## After this plan

- **Plan 2b, the student screens**, gets written next. It works against `docs/bridge.md` as built. It covers:
  - the Vite + TypeScript page in `ui/`;
  - the Rhino-style canvas from `plan2-notes.md` "Visual direction": grid, axes from Home, the paper, unreachable gray, pieces with their preview images, selection handles, the live pen dot, and the animated plan;
  - the step bar and instruction line;
  - the Pens panel, tool column, Osnap-style snapping and status bar;
  - Fluent UI controls, the dialogs (pen change, close mid-plot, errors with Details and Copy diagnostics), the Advanced dialog, inch/mm display, and keyboard access.
- **Plan 1's Task 20** (real Illustrator and Affinity exports) and **Task 21** (first hardware plots) are still open. They don't block Plan 2b.
- Things the hardware sessions should check for this layer: Step 11 above, plus the `plan2-notes.md` hardware checklist.
