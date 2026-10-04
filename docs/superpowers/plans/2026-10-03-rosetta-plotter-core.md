# Rosetta Plotter Core (Plan 1 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Rosetta Plotter's headless core and a `rosetta-plot` command-line tool. The core imports SVG/PDF/AI artwork, places it on paper, writes an EMS-ready plot file, and estimates, traces, pauses, resumes, and plots it on a real AxiDraw.

**Architecture:** The pure-Python modules under `src/rosetta/` do the "translator" work from the spec (§6.2): normalize, inline CSS, flatten via the EMS digest parser, place, clip, and group by color. `src/rosetta/engine/` wraps the unmodified EMS `pyaxidraw` 3.9.6 API for plotting, previews, and interactive moves. Everything is in millimetres in the machine frame (spec §4). The CLI is a thin layer over these modules, and the Plan 2 UI will call the same functions.

**Tech Stack:** Python 3.12 at `C:\Users\leona\AppData\Local\Programs\Python\Python312\python.exe` (this machine's `py -3.12` launcher entry is stale), with the EMS-tested engine dependencies pinned in `constraints.txt`. Also EMS AxiDraw API 3.9.6 (`pyaxidraw`, `axidrawinternal`, `plotink`, `ink_extensions`), lxml, tinycss2, PyMuPDF, pytest. Windows PowerShell commands.

**Spec:** `docs/superpowers/specs/2026-10-03-rosetta-plotter-design.md`

**Later plans:**
- **Plan 2:** the student-facing pywebview/WebView2 app (§5, §6.4, §6.5).
- **Plan 3:** packaging, installer, Quick Start, and GitHub release (§2, §11.5).

Both get written after this plan is done.

**Conventions for every task:**
- Run all commands from the repo root `C:\Users\leona\Projects\rosetta-plotter` in PowerShell.
- Tests run with `.venv\Scripts\python -m pytest`.
- Every commit ends with the trailer `-m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, `rosetta-plot` entry point, pytest config |
| `vendor/AxiDraw_API.zip` | Pinned copy of the EMS AxiDraw API 3.9.6 (GPL, redistributable) |
| `src/rosetta/__init__.py` | Version string |
| `src/rosetta/errors.py` | `ImportProblem`, whose message is shown to students as-is |
| `src/rosetta/units.py` | Parse SVG lengths, convert to mm |
| `src/rosetta/colors.py` | SVG paint → `#rrggbb` pen color; everyday color names |
| `src/rosetta/models.py` | AxiDraw model travel table; pen types |
| `src/rosetta/svgdoc.py` | Parse SVG, detect the source app, normalize page size/viewBox, inline CSS |
| `src/rosetta/flatten.py` | Normalized SVG → `Shape`s (polylines in mm, color, stroked/filled) via EMS digest |
| `src/rosetta/issues.py` | Problem checker (spec §6.3) |
| `src/rosetta/pdf_import.py` | PDF / PDF-compatible AI page → SVG text via PyMuPDF |
| `src/rosetta/loader.py` | `load_artwork(path)`: dispatch by extension, run checks, return `Artwork` |
| `src/rosetta/geometry.py` | Rotation/scale/translate, bbox, rect intersect, polyline clipping |
| `src/rosetta/compose.py` | Material, Placement, `compose_job`, `initial_placement` |
| `src/rosetta/plotsvg.py` | Write the plot-ready SVG (one layer per pen color) |
| `src/rosetta/engine/options.py` | `PlotSettings`, `apply_settings`, `make_axidraw` |
| `src/rosetta/engine/identity.py` | Model stored in the plotter nickname (spec §8) |
| `src/rosetta/engine/awake.py` | Keep Windows awake during plots |
| `src/rosetta/engine/runner.py` | Estimates, plot runs with progress, pause/resume |
| `src/rosetta/engine/plotter.py` | Interactive control: connect, home, jog, pen height, trace, identity |
| `src/rosetta/cli.py` | `rosetta-plot` commands: prepare, estimate, info, identify, trace, plot |
| `tests/samples.py` | Synthetic SVG strings that mimic Illustrator, Affinity, Inkscape, generic exports |
| `tests/files/real/` | Real exports from Illustrator 2026 and Affinity 3.3 (Task 20) |

---

### Task 1: Project scaffold, environment, and pinned EMS engine

**Files:**
- Create: `.gitignore`, `pyproject.toml`, `README.md`, `src/rosetta/__init__.py`, `src/rosetta/errors.py`, `src/rosetta/engine/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`
- Create: `vendor/AxiDraw_API.zip` (downloaded)

- [ ] **Step 1: Initialize git and check identity**

```powershell
git init
git config user.name
git config user.email
```
Expected: `Initialized empty Git repository…`, followed by a name and an email.
- If either prints nothing, stop and ask Adam for the name and email to use.
- Then set them with `git config user.name "…"` and `git config user.email "…"`.

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
build/
dist/
out/
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "rosetta-plotter"
version = "0.1.0"
description = "Step-by-step pen plotting for AxiDraw machines"
requires-python = ">=3.12,<3.13"
license = "AGPL-3.0-or-later"
dependencies = [
    "lxml>=5.0",
    "tinycss2>=1.3",
    "pymupdf>=1.24",
]
# The EMS AxiDraw API (pyaxidraw) is not on PyPI. Install it from vendor/AxiDraw_API.zip.

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
rosetta-plot = "rosetta.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/rosetta"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 4: Create the package files**

`src/rosetta/__init__.py`:
```python
"""Rosetta Plotter: step-by-step pen plotting for AxiDraw machines."""

__version__ = "0.1.0"
```

`src/rosetta/errors.py`:
```python
"""Errors whose message is shown to the student exactly as written."""


class ImportProblem(Exception):
    """A file can't be used. str(exc) is a plain-language message for the student."""
```

`src/rosetta/engine/__init__.py`:
```python
"""Wrappers around the EMS AxiDraw engine (pyaxidraw)."""
```

`tests/__init__.py`: empty file.

`README.md`:
```markdown
# Rosetta Plotter

Step-by-step pen plotting for Evil Mad Scientist AxiDraw machines, built for students.
Windows only. Licensed AGPL-3.0-or-later. Bundles the EMS AxiDraw API (GPL).

Developer setup:

    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install vendor\AxiDraw_API.zip
    .venv\Scripts\python -m pip install -e ".[dev]"
    .venv\Scripts\python -m pytest
```

- [ ] **Step 5: Write the smoke test**

`tests/test_smoke.py`:
```python
import rosetta


def test_version():
    assert rosetta.__version__ == "0.1.0"
```

- [ ] **Step 6: Download the EMS API and create the environment**

```powershell
New-Item -ItemType Directory -Force vendor | Out-Null
Invoke-WebRequest -Uri https://cdn.evilmadscientist.com/dl/ad/public/AxiDraw_API.zip -OutFile vendor\AxiDraw_API.zip
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install vendor\AxiDraw_API.zip
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -c "from pyaxidraw import axidraw; print(axidraw.AxiDraw().version_string)"
```
Expected: the last command prints `3.9.6`. If EMS has published a newer version, continue anyway; Task 2's contract test decides whether it's compatible.

- [ ] **Step 7: Run the smoke test**

Run: `.venv\Scripts\python -m pytest tests\test_smoke.py -v`
Expected: `1 passed`

- [ ] **Step 8: Commit**

```powershell
git add .gitignore pyproject.toml README.md src tests vendor docs
git commit -m "chore: scaffold Rosetta Plotter with pinned EMS AxiDraw API" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Engine contract test

This test pins down every EMS internal the core relies on. If a future EMS update renames one of them, this test fails first and points at the cause.

**Files:**
- Test: `tests/test_engine_contract.py`

- [ ] **Step 1: Write the contract test**

```python
"""Everything Rosetta Plotter uses from the EMS engine, checked in one place.

If this fails after an EMS update, compare the failing name with the new EMS source
before changing any Rosetta code.
"""
from importlib.metadata import version

from axidrawinternal import digest_svg, plot_warnings
from ink_extensions import simpletransform
from plotink import ebb_motion, ebb_serial, plot_utils
from pyaxidraw import axidraw


def test_engine_version_is_pinned():
    assert axidraw.AxiDraw().version_string == "3.9.6"


def test_engine_dependencies_match_ems_tested_versions():
    # Name checks can't catch version drift; constraints.txt pins these to EMS's tested set.
    assert version("plotink") == "1.9.0"
    assert version("ink_extensions") == "2.0.0"
    assert version("pyserial") == "3.5"


def test_internal_attributes_used_by_runner():
    ad = axidraw.AxiDraw()
    assert callable(ad.set_up_pause_receiver)
    assert hasattr(ad.plot_status, "stopped")
    assert hasattr(ad.plot_status.stats, "pt_estimate")
    assert hasattr(ad.plot_status.stats, "down_travel_inch")
    assert hasattr(ad.plot_status.stats, "down_travel_tot")
    assert hasattr(ad.pen.phys, "xpos")
    assert hasattr(ad.pen.phys, "ypos")


def test_helpers_used_by_plotter_and_flatten():
    for function in (
        ebb_motion.queryVoltage,
        ebb_motion.sendDisableMotors,
        ebb_serial.query_nickname,
        ebb_serial.write_nickname,
        ebb_serial.reboot,
        ebb_serial.min_version,
        ebb_serial.queryVersion,
        plot_utils.vb_scale,
        simpletransform.parseTransform,
        digest_svg.DigestSVG,
        plot_warnings.PlotWarnings,
    ):
        assert callable(function)
```

- [ ] **Step 2: Run it**

Run: `.venv\Scripts\python -m pytest tests\test_engine_contract.py -v`
Expected: `4 passed`.
- If only `test_engine_version_is_pinned` fails because the version is newer and the other two pass, the newer engine is compatible. Change the expected string to the installed version and update the version in spec §3.
- If either of the other two fails, stop. Report the missing name to Adam before going further.

- [ ] **Step 3: Commit**

```powershell
git add tests\test_engine_contract.py
git commit -m "test: pin EMS engine internals used by Rosetta" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Units

**Files:**
- Create: `src/rosetta/units.py`
- Test: `tests/test_units.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from rosetta.units import MM_PER_INCH, length_to_mm, parse_length


def test_parse_length_splits_value_and_unit():
    assert parse_length("12.5mm") == (12.5, "mm")
    assert parse_length(" 100% ") == (100.0, "%")
    assert parse_length("612") == (612.0, "")
    assert parse_length("1e2PX") == (100.0, "px")


def test_parse_length_rejects_junk():
    assert parse_length("abc") == (None, "")
    assert parse_length(None) == (None, "")


def test_length_to_mm_absolute_units():
    assert length_to_mm("1in", 96) == pytest.approx(MM_PER_INCH)
    assert length_to_mm("72pt", 96) == pytest.approx(25.4)
    assert length_to_mm("2cm", 96) == pytest.approx(20.0)
    assert length_to_mm("6pc", 96) == pytest.approx(25.4)


def test_length_to_mm_implicit_units_use_px_per_inch():
    assert length_to_mm("96", 96) == pytest.approx(25.4)
    assert length_to_mm("72px", 72) == pytest.approx(25.4)


def test_length_to_mm_unsupported_returns_none():
    assert length_to_mm("50%", 96) is None
    assert length_to_mm("3em", 96) is None
    assert length_to_mm(None, 96) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_units.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.units'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/units.py`:
```python
"""Length parsing and conversion. Everything inside Rosetta Plotter is millimetres."""
import re

MM_PER_INCH = 25.4

_ABSOLUTE_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "in": MM_PER_INCH,
    "pt": MM_PER_INCH / 72,
    "pc": MM_PER_INCH / 6,
    "q": 0.25,
}

_LENGTH = re.compile(r"\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Z%]*)\s*")


def parse_length(text: str | None) -> tuple[float | None, str]:
    """Split '12.5mm' into (12.5, 'mm'). Unitless gives ''. Unparseable gives (None, '')."""
    if text is None:
        return None, ""
    match = _LENGTH.fullmatch(text)
    if not match:
        return None, ""
    return float(match.group(1)), match.group(2).lower()


def length_to_mm(text: str | None, px_per_inch: float) -> float | None:
    """Convert an SVG length to mm. Unitless and 'px' use px_per_inch. None for %, em, or junk."""
    value, unit = parse_length(text)
    if value is None:
        return None
    if unit in ("", "px"):
        return value * MM_PER_INCH / px_per_inch
    factor = _ABSOLUTE_MM.get(unit)
    return None if factor is None else value * factor
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_units.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\units.py tests\test_units.py
git commit -m "feat: SVG length parsing and mm conversion" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Colors

**Files:**
- Create: `src/rosetta/colors.py`
- Test: `tests/test_colors.py`

- [ ] **Step 1: Write the failing test**

```python
from rosetta.colors import BLACK, WHITE, color_name, resolve_paint


def test_resolve_paint_normalizes_to_hex():
    assert resolve_paint("#f00", default=None) == "#ff0000"
    assert resolve_paint("red", default=None) == "#ff0000"
    assert resolve_paint("rgb(0, 0, 255)", default=None) == "#0000ff"
    assert resolve_paint("#FFFFFF", default=None) == WHITE


def test_resolve_paint_none_and_transparent_mean_no_paint():
    assert resolve_paint("none", default=None) is None
    assert resolve_paint("rgba(0,0,0,0)", default=None) is None
    assert resolve_paint(None, default=None) is None


def test_resolve_paint_uses_default_when_unset():
    # SVG's default fill is black.
    assert resolve_paint(None, default="black") == BLACK


def test_resolve_paint_unknown_paints_count_as_black():
    assert resolve_paint("url(#gradient1)", default=None) == BLACK
    assert resolve_paint("currentColor", default=None) == BLACK


def test_color_name_finds_nearest_everyday_name():
    assert color_name("#e30613") == "red"
    assert color_name("#000000") == "black"
    assert color_name("#0000ff") == "blue"
    assert color_name("#7f7f7f") == "gray"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_colors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.colors'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/colors.py`:
```python
"""SVG paint values to pen colors."""
import tinycss2.color3

WHITE = "#ffffff"
BLACK = "#000000"

_EVERYDAY = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "pink": (255, 192, 203),
    "brown": (139, 69, 19),
    "gray": (128, 128, 128),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
}


def resolve_paint(value: str | None, default: str | None) -> str | None:
    """Return '#rrggbb' for visible paint, or None for no paint.

    Gradients, patterns, and currentColor can't be known here, so they count as black.
    """
    if value is None:
        value = default
    if value is None:
        return None
    text = value.strip()
    if text.lower() in ("", "none", "transparent"):
        return None
    if text.lower().startswith("url("):
        return BLACK
    parsed = tinycss2.color3.parse_color(text)
    if parsed is None or isinstance(parsed, str):  # junk, or the string 'currentColor'
        return BLACK
    if parsed.alpha == 0:
        return None
    return "#{:02x}{:02x}{:02x}".format(
        round(parsed.red * 255), round(parsed.green * 255), round(parsed.blue * 255)
    )


def color_name(hex_color: str) -> str:
    """Closest everyday color name, for prompts like 'Load the red pen'."""
    rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return min(
        _EVERYDAY,
        key=lambda name: sum((a - b) ** 2 for a, b in zip(rgb, _EVERYDAY[name])),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_colors.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\colors.py tests\test_colors.py
git commit -m "feat: resolve SVG paints to pen colors and color names" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Machine models and pen types

**Files:**
- Create: `src/rosetta/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from rosetta.models import MODELS, PEN_TYPES, PEN_UP_SPEED, get_model


def test_all_seven_ems_models_present():
    assert sorted(MODELS) == [1, 2, 3, 4, 5, 6, 7]


def test_travel_matches_ems_inches_times_25_4():
    x, y = get_model(5).travel_mm  # SE/A1: 34.02 x 23.39 in
    assert x == pytest.approx(864.108)
    assert y == pytest.approx(594.106)
    assert get_model(1).travel_mm == pytest.approx((299.974, 217.932))


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        get_model(9)


def test_pen_types():
    assert PEN_TYPES["fineliner"].speed_pendown == 25
    assert PEN_TYPES["marker"].speed_pendown == 35
    assert PEN_TYPES["brush"].speed_pendown == 12
    assert PEN_UP_SPEED == 75
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.models'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/models.py`:
```python
"""AxiDraw models and pen types.

Travel limits are copied from EMS axidraw_conf.py (inches) and converted with x 25.4,
so Rosetta's limits match the engine's exactly.
"""
from dataclasses import dataclass

from rosetta.units import MM_PER_INCH


@dataclass(frozen=True)
class MachineModel:
    number: int  # the EMS 'model' option value
    name: str
    travel_x_in: float
    travel_y_in: float

    @property
    def travel_mm(self) -> tuple[float, float]:
        return (self.travel_x_in * MM_PER_INCH, self.travel_y_in * MM_PER_INCH)


MODELS = {
    model.number: model
    for model in (
        MachineModel(1, "AxiDraw V2 / V3 / SE/A4", 11.81, 8.58),
        MachineModel(2, "AxiDraw V3/A3 or SE/A3", 16.93, 11.69),
        MachineModel(3, "AxiDraw V3 XLX", 23.42, 8.58),
        MachineModel(4, "AxiDraw MiniKit", 6.30, 4.00),
        MachineModel(5, "AxiDraw SE/A1", 34.02, 23.39),
        MachineModel(6, "AxiDraw SE/A2", 23.39, 17.01),
        MachineModel(7, "AxiDraw V3/B6", 7.48, 5.51),
    )
}


def get_model(number: int) -> MachineModel:
    try:
        return MODELS[number]
    except KeyError:
        raise ValueError(f"Unknown AxiDraw model number: {number}") from None


@dataclass(frozen=True)
class PenType:
    key: str
    label: str
    speed_pendown: int  # percent of maximum, EMS 'speed_pendown'


PEN_TYPES = {
    pen.key: pen
    for pen in (
        PenType("fineliner", "Fine liner", 25),
        PenType("marker", "Marker", 35),
        PenType("brush", "Brush / paint pen", 12),
    )
}

PEN_UP_SPEED = 75  # percent, same for all pen types
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_models.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\models.py tests\test_models.py
git commit -m "feat: AxiDraw model travel table and pen types" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: SVG normalization (page size, viewBox, source detection)

**Files:**
- Create: `src/rosetta/svgdoc.py`
- Create: `tests/samples.py`
- Test: `tests/test_svgdoc.py`

- [ ] **Step 1: Create the synthetic samples**

`tests/samples.py`:
```python
"""Synthetic SVGs that mimic what each app exports. Real exports are tested in Task 20."""

# Illustrator "Export As" with Responsive on: no width/height, viewBox in points, CSS classes.
# 283.4646 pt = 100 mm.
ILLUSTRATOR_EXPORT = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg id="Layer_1" data-name="Layer 1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 566.9291 283.4646">
  <defs><style>.cls-1{fill:none;stroke:#ff0000;stroke-miterlimit:10;}.cls-2{fill:#0000ff;}</style></defs>
  <rect class="cls-1" x="0" y="0" width="283.4646" height="283.4646"/>
  <circle class="cls-2" cx="425.1969" cy="141.7323" r="70.8661"/>
</svg>"""

# Illustrator "Save As" style: px sizes that really mean points (EMS process_ai fix).
ILLUSTRATOR_PX = b"""<?xml version="1.0" encoding="utf-8"?>
<!-- Generator: Adobe Illustrator 30.8.1, SVG Export Plug-In . SVG Version: 6.00 Build 0)  -->
<svg version="1.1" xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="612px" height="792px" viewBox="0 0 612 792">
  <line fill="none" stroke="#000000" x1="72" y1="72" x2="144" y2="72"/>
</svg>"""

# Affinity: percent sizes, serif namespace, inline styles. 377.95276 px @96 = 100 mm.
AFFINITY_EXPORT = b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="100%" height="100%" viewBox="0 0 377.95276 188.97638" version="1.1"
     xmlns="http://www.w3.org/2000/svg" xmlns:serif="http://www.serif.com/"
     style="fill-rule:evenodd;clip-rule:evenodd;stroke-linejoin:round;">
  <g id="Layer1" serif:id="Layer 1">
    <path d="M37.795276,37.795276L377.95276,37.795276" style="fill:none;stroke:#00f;stroke-width:1px;"/>
  </g>
</svg>"""

# Inkscape: real units and an Inkscape layer.
INKSCAPE_MM = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="100mm" height="50mm" viewBox="0 0 100 50" version="1.1"
     xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">
  <g inkscape:groupmode="layer" inkscape:label="Layer 1">
    <path d="M 10,10 L 90,10 L 90,40" style="fill:none;stroke:#000000;stroke-width:0.3"/>
  </g>
</svg>"""

# Generic hand-written SVG: unitless size, no viewBox -> CSS px at 96 per inch.
GENERIC_PX = b"""<svg xmlns="http://www.w3.org/2000/svg" width="96" height="48">
  <line x1="0" y1="0" x2="96" y2="48" stroke="black"/>
</svg>"""

NO_SIZE = b"""<svg xmlns="http://www.w3.org/2000/svg"><line x1="0" y1="0" x2="1" y2="1" stroke="black"/></svg>"""

WITH_PROBLEMS = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="100mm" height="100mm" viewBox="0 0 100 100">
  <defs><text id="hidden">not counted</text><clipPath id="c"><rect width="50" height="50"/></clipPath></defs>
  <text x="10" y="10">Hello</text>
  <image x="0" y="0" width="10" height="10" xlink:href="photo.png"/>
  <g clip-path="url(#c)"><line x1="0" y1="0" x2="100" y2="100" stroke="black"/></g>
  <rect x="0" y="0" width="100" height="100" fill="#ffffff"/>
  <circle cx="50" cy="50" r="20" fill="#00ff00"/>
</svg>"""
```

- [ ] **Step 2: Write the failing test**

`tests/test_svgdoc.py`:
```python
import pytest

from rosetta.errors import ImportProblem
from rosetta.svgdoc import detect_source, normalize
from tests import samples


def test_detect_source():
    assert normalize(samples.ILLUSTRATOR_EXPORT).source == "illustrator"
    assert normalize(samples.ILLUSTRATOR_PX).source == "illustrator"
    assert normalize(samples.AFFINITY_EXPORT).source == "affinity"
    assert normalize(samples.INKSCAPE_MM).source == "inkscape"
    assert normalize(samples.GENERIC_PX).source == "svg"


def test_illustrator_viewbox_is_points():
    doc = normalize(samples.ILLUSTRATOR_EXPORT)
    assert doc.width_mm == pytest.approx(200.0, abs=0.001)
    assert doc.height_mm == pytest.approx(100.0, abs=0.001)


def test_illustrator_px_means_points():
    doc = normalize(samples.ILLUSTRATOR_PX)
    assert (doc.width_mm, doc.height_mm) == pytest.approx((215.9, 279.4))


def test_affinity_percent_falls_back_to_viewbox():
    doc = normalize(samples.AFFINITY_EXPORT)
    assert (doc.width_mm, doc.height_mm) == pytest.approx((100.0, 50.0), abs=0.001)


def test_inkscape_mm_kept():
    doc = normalize(samples.INKSCAPE_MM)
    assert (doc.width_mm, doc.height_mm) == pytest.approx((100.0, 50.0))


def test_generic_without_viewbox_gets_one():
    doc = normalize(samples.GENERIC_PX)
    assert (doc.width_mm, doc.height_mm) == pytest.approx((25.4, 12.7))
    assert doc.root.get("viewBox") == "0.000000 0.000000 96.000000 48.000000"


def test_root_rewritten_in_mm():
    doc = normalize(samples.ILLUSTRATOR_EXPORT)
    assert doc.root.get("width") == "200.000000mm"
    assert doc.root.get("height") == "100.000000mm"


def test_pdf_hint_overrides_detection():
    assert normalize(samples.GENERIC_PX, source_hint="pdf").source == "pdf"


def test_no_size_is_an_import_problem():
    with pytest.raises(ImportProblem, match="no page size"):
        normalize(samples.NO_SIZE)


def test_not_svg_is_an_import_problem():
    with pytest.raises(ImportProblem):
        normalize(b"hello")
    with pytest.raises(ImportProblem):
        normalize(b"<html></html>")


def test_detect_source_direct():
    doc = normalize(samples.INKSCAPE_MM)
    assert detect_source(doc.root, samples.INKSCAPE_MM) == "inkscape"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_svgdoc.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.svgdoc'`

- [ ] **Step 4: Write the implementation**

`src/rosetta/svgdoc.py`:
```python
"""Read an SVG from any app and normalize it.

After normalize(): the root has width/height in mm and a viewBox, and <style> rules have
been copied onto elements (see inline_css), so the EMS parser reads the file the way the
student's app drew it.
"""
from dataclasses import dataclass

from lxml import etree

from rosetta.errors import ImportProblem
from rosetta.units import MM_PER_INCH, length_to_mm, parse_length

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
SODIPODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
SERIF_NS = "http://www.serif.com/"

# What an app means by a size with no unit (or 'px'), in units per inch.
# Illustrator means points; EMS fixes the same thing in process_ai.py. PDF pages are points.
# Affinity is checked against a real Affinity 3.3 export in Task 20.
AFFINITY_PX_PER_INCH = 96.0
IMPLICIT_PX_PER_INCH = {
    "illustrator": 72.0,
    "affinity": AFFINITY_PX_PER_INCH,
    "inkscape": 96.0,
    "svg": 96.0,
    "pdf": 72.0,
}

_PARSER = etree.XMLParser(huge_tree=True, no_network=True)


@dataclass
class NormalizedSvg:
    root: etree._Element
    width_mm: float
    height_mm: float
    source: str  # 'illustrator' | 'affinity' | 'inkscape' | 'svg' | 'pdf'


def detect_source(root: etree._Element, raw: bytes) -> str:
    """Guess which app wrote this SVG from its fingerprints."""
    if b"Adobe Illustrator" in raw[:8192] or b".cls-1" in raw or root.xpath("//*[@data-name]"):
        return "illustrator"
    namespaces = set((root.nsmap or {}).values())
    if SERIF_NS in namespaces:
        return "affinity"
    if INKSCAPE_NS in namespaces or SODIPODI_NS in namespaces:
        return "inkscape"
    return "svg"


def normalize(raw: bytes, source_hint: str | None = None) -> NormalizedSvg:
    try:
        root = etree.fromstring(raw, parser=_PARSER)
    except etree.XMLSyntaxError as exc:
        raise ImportProblem("This file isn't a readable SVG.") from exc
    if not isinstance(root.tag, str) or etree.QName(root).localname != "svg":
        raise ImportProblem("This file isn't a readable SVG.")

    source = source_hint or detect_source(root, raw)
    px_per_inch = IMPLICIT_PX_PER_INCH[source]
    viewbox = _parse_viewbox(root.get("viewBox"))

    width_mm = length_to_mm(root.get("width"), px_per_inch)
    height_mm = length_to_mm(root.get("height"), px_per_inch)
    if width_mm is None or height_mm is None:
        if viewbox is None:
            raise ImportProblem("This file has no page size, so it can't be placed.")
        width_mm = viewbox[2] * MM_PER_INCH / px_per_inch
        height_mm = viewbox[3] * MM_PER_INCH / px_per_inch
    if width_mm <= 0 or height_mm <= 0:
        raise ImportProblem("This file's page size is zero.")
    if viewbox is None:
        viewbox = _implied_viewbox(root, width_mm, height_mm)

    root.set("width", f"{width_mm:.6f}mm")
    root.set("height", f"{height_mm:.6f}mm")
    root.set("viewBox", " ".join(f"{value:.6f}" for value in viewbox))
    return NormalizedSvg(root, width_mm, height_mm, source)


def _parse_viewbox(text: str | None) -> tuple[float, float, float, float] | None:
    if not text:
        return None
    parts = text.replace(",", " ").split()
    if len(parts) != 4:
        return None
    try:
        values = tuple(float(part) for part in parts)
    except ValueError:
        return None
    if values[2] <= 0 or values[3] <= 0:
        return None
    return values


def _implied_viewbox(root, width_mm: float, height_mm: float) -> tuple[float, float, float, float]:
    """No viewBox: user units are the unitless numbers if the size was unitless, else CSS px."""
    width_value, width_unit = parse_length(root.get("width"))
    height_value, height_unit = parse_length(root.get("height"))
    if width_value and height_value and width_unit in ("", "px") and height_unit in ("", "px"):
        return (0.0, 0.0, width_value, height_value)
    return (0.0, 0.0, width_mm * 96.0 / MM_PER_INCH, height_mm * 96.0 / MM_PER_INCH)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_svgdoc.py -v`
Expected: `11 passed`

- [ ] **Step 6: Commit**

```powershell
git add src\rosetta\svgdoc.py tests\samples.py tests\test_svgdoc.py
git commit -m "feat: normalize SVG page size per source app" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Inline CSS so the EMS parser sees Illustrator's colors

**Files:**
- Modify: `src/rosetta/svgdoc.py` (add `inline_css` and helpers; call it from `normalize`)
- Test: `tests/test_inline_css.py`

- [ ] **Step 1: Write the failing test**

```python
from lxml import etree

from rosetta.svgdoc import inline_css, normalize
from tests import samples

SVG = "http://www.w3.org/2000/svg"


def _root(body: str):
    return etree.fromstring(
        f'<svg xmlns="{SVG}" width="10mm" height="10mm" viewBox="0 0 10 10">{body}</svg>'.encode()
    )


def _style(element) -> dict:
    return dict(p.split(":", 1) for p in element.get("style").split(";") if p)


def test_class_rule_is_copied_to_style():
    root = _root('<style>.cls-1{fill:none;stroke:#ff0000}</style><rect class="cls-1" width="5" height="5"/>')
    inline_css(root)
    rect = root.find(f"{{{SVG}}}rect")
    assert _style(rect) == {"fill": "none", "stroke": "#ff0000"}


def test_inline_style_wins_over_stylesheet():
    root = _root('<style>.a{stroke:red}</style><rect class="a" style="stroke:blue" width="5" height="5"/>')
    inline_css(root)
    assert _style(root.find(f"{{{SVG}}}rect"))["stroke"] == "blue"


def test_specificity_id_beats_class_beats_tag():
    root = _root(
        "<style>#x{stroke:green} .a{stroke:red} rect{stroke:black}</style>"
        '<rect id="x" class="a" width="1" height="1"/><rect class="a" width="1" height="1"/>'
        '<rect width="1" height="1"/>'
    )
    inline_css(root)
    strokes = [_style(r)["stroke"] for r in root.iter(f"{{{SVG}}}rect")]
    assert strokes == ["green", "red", "black"]


def test_selector_lists_and_tag_with_class():
    root = _root('<style>.a, .b{stroke:red} path.c{fill:blue}</style>'
                 '<rect class="b" width="1" height="1"/><path class="c" d="M0,0 L1,1"/>')
    inline_css(root)
    assert _style(root.find(f"{{{SVG}}}rect"))["stroke"] == "red"
    assert _style(root.find(f"{{{SVG}}}path"))["fill"] == "blue"


def test_unsupported_selectors_are_ignored():
    root = _root('<style>g > rect{stroke:red} rect:hover{stroke:blue}</style><g><rect width="1" height="1"/></g>')
    inline_css(root)
    assert root.find(f".//{{{SVG}}}rect").get("style") is None


def test_normalize_runs_inline_css_on_illustrator_export():
    doc = normalize(samples.ILLUSTRATOR_EXPORT)
    rect = doc.root.find(f"{{{SVG}}}rect")
    assert "stroke:#ff0000" in rect.get("style")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_inline_css.py -v`
Expected: FAIL with `ImportError: cannot import name 'inline_css' from 'rosetta.svgdoc'`

- [ ] **Step 3: Write the implementation**

In `src/rosetta/svgdoc.py`, add these imports at the top with the others:
```python
import re

import tinycss2
```

In `normalize()`, add this line directly before `return NormalizedSvg(root, width_mm, height_mm, source)`:
```python
    inline_css(root)
```

Then add these functions at the end of the file:
```python
_SIMPLE_SELECTOR = re.compile(r"^(?P<tag>[A-Za-z][\w-]*)?(?P<rest>(?:[.#][\w-]+)*)$")


def inline_css(root: etree._Element) -> None:
    """Copy <style> rules onto each element's style attribute.

    The EMS parser ignores <style>, and Illustrator's default export puts every color in
    CSS classes. Supports simple selectors only (tag, .class, #id, and combinations like
    path.cls-1); others are skipped. An element's own style attribute wins.
    """
    rules = []
    for style_element in root.iter(f"{{{SVG_NS}}}style", "style"):
        for rule in tinycss2.parse_stylesheet(
            style_element.text or "", skip_comments=True, skip_whitespace=True
        ):
            if rule.type != "qualified-rule":
                continue
            declarations = {
                declaration.name.lower(): tinycss2.serialize(declaration.value).strip()
                for declaration in tinycss2.parse_declaration_list(
                    rule.content, skip_comments=True, skip_whitespace=True
                )
                if declaration.type == "declaration"
            }
            for selector_text in tinycss2.serialize(rule.prelude).split(","):
                parsed = _parse_selector(selector_text.strip())
                if parsed is not None:
                    specificity, matcher = parsed
                    rules.append((specificity, len(rules), matcher, declarations))
    if not rules:
        return
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        matched = sorted(
            (specificity, order, declarations)
            for specificity, order, matcher, declarations in rules
            if matcher(element)
        )
        if not matched:
            continue
        merged: dict[str, str] = {}
        for _specificity, _order, declarations in matched:
            merged.update(declarations)
        merged.update(_parse_style_attribute(element.get("style")))
        element.set("style", ";".join(f"{key}:{value}" for key, value in merged.items()))


def _parse_selector(text: str):
    """Return (specificity, matcher) for a simple selector, or None if unsupported."""
    match = _SIMPLE_SELECTOR.match(text)
    if not text or not match:
        return None
    tag = match.group("tag")
    parts = re.findall(r"[.#][\w-]+", match.group("rest"))
    classes = {part[1:] for part in parts if part[0] == "."}
    ids = {part[1:] for part in parts if part[0] == "#"}

    def matcher(element) -> bool:
        if tag and etree.QName(element).localname != tag:
            return False
        if ids and element.get("id") not in ids:
            return False
        if classes and not classes.issubset((element.get("class") or "").split()):
            return False
        return True

    return (len(ids), len(classes), 1 if tag else 0), matcher


def _parse_style_attribute(text: str | None) -> dict[str, str]:
    result = {}
    for part in (text or "").split(";"):
        if ":" in part:
            key, value = part.split(":", 1)
            if key.strip():
                result[key.strip().lower()] = value.strip()
    return result
```

- [ ] **Step 4: Run all svgdoc tests**

Run: `.venv\Scripts\python -m pytest tests\test_inline_css.py tests\test_svgdoc.py -v`
Expected: `17 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\svgdoc.py tests\test_inline_css.py
git commit -m "feat: inline CSS rules so Illustrator class colors reach the EMS parser" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Flatten through the EMS digest parser

**Files:**
- Create: `src/rosetta/flatten.py`
- Test: `tests/test_flatten.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from rosetta.flatten import Shape, flatten
from rosetta.geometry_testing import shapes_bbox
from rosetta.svgdoc import normalize
from tests import samples


def _by_color(shapes):
    result = {}
    for shape in shapes:
        result.setdefault(shape.color, []).append(shape)
    return result


def test_illustrator_square_and_circle_in_mm():
    shapes = flatten(normalize(samples.ILLUSTRATOR_EXPORT))
    groups = _by_color(shapes)
    assert set(groups) == {"#ff0000", "#0000ff"}
    assert shapes_bbox(groups["#ff0000"]) == pytest.approx((0, 0, 100, 100), abs=0.01)
    assert shapes_bbox(groups["#0000ff"]) == pytest.approx((125, 25, 175, 75), abs=0.05)


def test_stroked_and_filled_flags():
    groups = _by_color(flatten(normalize(samples.ILLUSTRATOR_EXPORT)))
    square, = groups["#ff0000"]
    circle, = groups["#0000ff"]
    assert (square.stroked, square.filled) == (True, False)
    assert (circle.stroked, circle.filled) == (False, True)


def test_affinity_line_in_mm():
    shapes = flatten(normalize(samples.AFFINITY_EXPORT))
    assert len(shapes) == 1
    assert shapes[0].color == "#0000ff"
    assert shapes[0].polylines[0][0] == pytest.approx((10.0, 10.0), abs=0.001)
    assert shapes[0].polylines[0][-1] == pytest.approx((100.0, 10.0), abs=0.001)


def test_illustrator_px_line_is_points():
    shape, = flatten(normalize(samples.ILLUSTRATOR_PX))
    assert shape.polylines[0][0] == pytest.approx((25.4, 25.4), abs=0.001)
    assert shape.polylines[0][-1] == pytest.approx((50.8, 25.4), abs=0.001)


def test_generic_unitless_line():
    shape, = flatten(normalize(samples.GENERIC_PX))
    assert shape.polylines[0][-1] == pytest.approx((25.4, 12.7), abs=0.001)


def test_invisible_shapes_dropped_and_default_fill_is_black():
    raw = b"""<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">
      <rect width="5" height="5" fill="none"/>
      <rect x="5" y="5" width="5" height="5"/>
      <line x1="0" y1="0" x2="10" y2="10"/>
    </svg>"""
    shapes = flatten(normalize(raw))
    # The fill="none" rect has no stroke: invisible. The bare rect is black-filled.
    # The bare line has no stroke and lines can't be filled: invisible.
    assert len(shapes) == 1
    assert isinstance(shapes[0], Shape)
    assert shapes[0].color == "#000000"
    assert (shapes[0].stroked, shapes[0].filled) == (False, True)
```

This test uses a tiny test helper. Create `src/rosetta/geometry_testing.py`:
```python
"""Small helpers shared by tests (kept in the package so tests import one place)."""


def shapes_bbox(shapes) -> tuple[float, float, float, float]:
    xs = [x for shape in shapes for polyline in shape.polylines for x, _ in polyline]
    ys = [y for shape in shapes for polyline in shape.polylines for _, y in polyline]
    return (min(xs), min(ys), max(xs), max(ys))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_flatten.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.flatten'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/flatten.py`:
```python
"""Normalized SVG -> Shapes, using the EMS digest parser.

Using EMS's own parser means what Rosetta shows on screen is what the engine will draw:
same transforms, same handling of <use>/<symbol>, same curve tolerance (0.002 in).
"""
from dataclasses import dataclass

from axidrawinternal import digest_svg, plot_warnings
from ink_extensions import simpletransform
from plotink import plot_utils

from rosetta.colors import resolve_paint
from rosetta.svgdoc import NormalizedSvg
from rosetta.units import MM_PER_INCH

CURVE_TOLERANCE_IN = 0.002  # EMS default curve_tolerance (0.05 mm)

Polyline = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Shape:
    """One SVG drawing element, as straight-line polylines in mm (document coordinates)."""

    polylines: tuple[Polyline, ...]
    color: str  # '#rrggbb': the stroke color, or the fill color for fill-only shapes
    stroked: bool
    filled: bool


def flatten(doc: NormalizedSvg) -> list[Shape]:
    root = doc.root
    width_in = doc.width_mm / MM_PER_INCH
    height_in = doc.height_mm / MM_PER_INCH
    # Same document transform EMS builds in AxiDraw.prepare_document().
    s_x, s_y, o_x, o_y = plot_utils.vb_scale(
        root.get("viewBox"), root.get("preserveAspectRatio"), width_in, height_in
    )
    transform = simpletransform.parseTransform(
        f"scale({s_x:.6E},{s_y:.6E}) translate({o_x:.6E},{o_y:.6E})"
    )
    digester = digest_svg.DigestSVG(default_logging=False)
    digest = digester.process_svg(
        root,
        plot_warnings.PlotWarnings(),
        [width_in, height_in, s_x, s_y, -2, CURVE_TOLERANCE_IN],
        transform,
    )

    shapes = []
    for layer in digest.layers:
        for item in layer.paths:
            subpaths = [subpath for subpath in item.subpaths if len(subpath) >= 2]
            if not subpaths:
                continue
            stroke = resolve_paint(item.stroke, default=None)
            fill = resolve_paint(item.fill, default="black")  # SVG's default fill is black
            if all(len(subpath) == 2 for subpath in subpaths):
                fill = None  # single segments enclose no area; EMS strips their fill too
            if stroke is None and fill is None:
                continue  # invisible helper shape
            polylines = tuple(
                tuple((x * MM_PER_INCH, y * MM_PER_INCH) for x, y in subpath)
                for subpath in subpaths
            )
            shapes.append(Shape(polylines, stroke or fill, stroke is not None, fill is not None))
    return shapes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_flatten.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\flatten.py src\rosetta\geometry_testing.py tests\test_flatten.py
git commit -m "feat: flatten normalized SVG via EMS digest parser" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Problem checker

**Files:**
- Create: `src/rosetta/issues.py`
- Test: `tests/test_issues.py`

- [ ] **Step 1: Write the failing test**

```python
from rosetta.flatten import flatten
from rosetta.issues import MESSAGES, pdf_text_issue, scan_document, scan_shapes
from rosetta.svgdoc import normalize
from tests import samples


def _codes(issues):
    return {issue.code: issue.count for issue in issues}


def test_document_scan_counts_text_image_clip_but_not_defs():
    doc = normalize(samples.WITH_PROBLEMS)
    assert _codes(scan_document(doc.root, doc.source)) == {"text": 1, "image": 1, "clip": 1}


def test_clip_not_reported_for_pdf_sources():
    doc = normalize(samples.WITH_PROBLEMS, source_hint="pdf")
    assert "clip" not in _codes(scan_document(doc.root, doc.source))


def test_affinity_clip_rule_is_not_a_clip():
    doc = normalize(samples.AFFINITY_EXPORT)
    assert scan_document(doc.root, doc.source) == []


def test_shape_scan_counts_fill_only_and_white():
    shapes = flatten(normalize(samples.WITH_PROBLEMS))
    codes = _codes(scan_shapes(shapes))
    assert codes["white"] == 1
    assert codes["fill_only"] == 2  # white background rect + green circle


def test_empty_is_blocking():
    issues = scan_shapes([])
    assert len(issues) == 1
    assert issues[0].code == "empty" and issues[0].blocking


def test_pdf_text_issue_and_plain_messages():
    assert pdf_text_issue().code == "pdf_text"
    for message in MESSAGES.values():
        assert message.endswith(".")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_issues.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.issues'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/issues.py`:
```python
"""Find things in a file that won't plot the way the student expects, and say so plainly."""
from dataclasses import dataclass

from lxml import etree

from rosetta.colors import WHITE
from rosetta.svgdoc import SVG_NS


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    count: int = 1
    blocking: bool = False


MESSAGES = {
    "text": "This file has live text, which can't be drawn. In Illustrator or Affinity, "
            "convert text to outlines and export again.",
    "image": "Pictures can't be drawn, only lines. The picture will be skipped.",
    "clip": "This file uses a clipping mask. The hidden parts will be drawn too. "
            "Release or expand the mask before exporting.",
    "fill_only": "Some shapes are solid fills. The plotter draws only their outlines.",
    "white": "There's a white shape here, probably a background. It will be skipped.",
    "pdf_text": "Text will be drawn as outlined letters (double lines).",
    "empty": "This file has no lines to draw.",
}

_NS = {"svg": SVG_NS}


def scan_document(root: etree._Element, source: str) -> list[Issue]:
    counts = {"text": 0, "image": 0, "clip": 0}
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        name = etree.QName(element).localname
        if name in ("text", "flowRoot") and not _in_defs(element):
            counts["text"] += 1
        elif name == "image" and not _in_defs(element):
            counts["image"] += 1
        # PDF conversions wrap content in clip groups, so masks can't be told apart there.
        if source != "pdf" and _uses_clip(element):
            counts["clip"] += 1
    return [Issue(code, MESSAGES[code], count) for code, count in counts.items() if count]


def scan_shapes(shapes) -> list[Issue]:
    if not shapes:
        return [Issue("empty", MESSAGES["empty"], blocking=True)]
    issues = []
    fill_only = sum(1 for shape in shapes if shape.filled and not shape.stroked)
    white = sum(1 for shape in shapes if shape.color == WHITE)
    if fill_only:
        issues.append(Issue("fill_only", MESSAGES["fill_only"], fill_only))
    if white:
        issues.append(Issue("white", MESSAGES["white"], white))
    return issues


def pdf_text_issue() -> Issue:
    return Issue("pdf_text", MESSAGES["pdf_text"])


def _in_defs(element) -> bool:
    return bool(element.xpath("ancestor::svg:defs", namespaces=_NS))


def _uses_clip(element) -> bool:
    if element.get("clip-path") or element.get("mask"):
        return True
    style = (element.get("style") or "").replace(" ", "")
    return "clip-path:url" in style or "mask:url" in style
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_issues.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\issues.py tests\test_issues.py
git commit -m "feat: problem checker for text, images, masks, fills, white shapes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: PDF and AI import

**Files:**
- Create: `src/rosetta/pdf_import.py`
- Test: `tests/test_pdf_import.py`

- [ ] **Step 1: Write the failing test**

```python
import shutil

import pymupdf
import pytest

from rosetta.errors import ImportProblem
from rosetta.flatten import flatten
from rosetta.geometry_testing import shapes_bbox
from rosetta.pdf_import import page_count, pdf_page_to_svg
from rosetta.svgdoc import normalize

MM = 72 / 25.4  # points per mm


@pytest.fixture
def sample_pdf(tmp_path):
    """Two pages. Page 1: a red 50 mm square at (10 mm, 10 mm) on a 100 x 80 mm page, plus text."""
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=100 * MM, height=80 * MM)
    page.draw_rect(pymupdf.Rect(10 * MM, 10 * MM, 60 * MM, 60 * MM), color=(1, 0, 0), width=1)
    page.insert_text((10 * MM, 75 * MM), "Hi", fontsize=12)
    doc.new_page(width=100 * MM, height=80 * MM)
    doc.save(path)
    doc.close()
    return path


def test_page_count(sample_pdf):
    assert page_count(sample_pdf) == 2


def test_pdf_page_becomes_svg_in_points(sample_pdf):
    svg_text, has_text = pdf_page_to_svg(sample_pdf, 0)
    assert has_text is True
    doc = normalize(svg_text.encode("utf-8"), source_hint="pdf")
    assert (doc.width_mm, doc.height_mm) == pytest.approx((100.0, 80.0), abs=0.01)
    red = [shape for shape in flatten(doc) if shape.color == "#ff0000"]
    assert shapes_bbox(red) == pytest.approx((10, 10, 60, 60), abs=0.05)


def test_ai_with_pdf_compatibility_opens(sample_pdf, tmp_path):
    ai_path = tmp_path / "drawing.ai"
    shutil.copy(sample_pdf, ai_path)
    svg_text, _ = pdf_page_to_svg(ai_path, 0)
    assert "<svg" in svg_text


def test_ai_without_pdf_compatibility_is_explained(tmp_path):
    ai_path = tmp_path / "old.ai"
    ai_path.write_bytes(b"%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator\n")
    with pytest.raises(ImportProblem, match="PDF Compatible"):
        pdf_page_to_svg(ai_path, 0)


def test_missing_page_is_explained(sample_pdf):
    with pytest.raises(ImportProblem, match="has 2 pages"):
        pdf_page_to_svg(sample_pdf, 5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_pdf_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.pdf_import'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/pdf_import.py`:
```python
"""PDF and PDF-compatible .ai pages -> SVG text, via PyMuPDF (text converted to outlines)."""
from pathlib import Path

import pymupdf
from lxml import etree

from rosetta.errors import ImportProblem

AI_NOT_PDF = (
    "This Illustrator file was saved without PDF compatibility. In Illustrator, use "
    "File › Save As and check “Create PDF Compatible File”, or export an SVG instead."
)


def page_count(path: Path) -> int:
    with _open(Path(path)) as doc:
        return doc.page_count


def pdf_page_to_svg(path: Path, page_index: int = 0) -> tuple[str, bool]:
    """Return (svg_text, has_text). The SVG's width and height are set in pt from the page."""
    with _open(Path(path)) as doc:
        if doc.page_count == 0:
            raise ImportProblem("This PDF has no pages.")
        if not 0 <= page_index < doc.page_count:
            raise ImportProblem(
                f"This PDF has {doc.page_count} pages; page {page_index + 1} doesn't exist."
            )
        page = doc[page_index]
        svg_text = page.get_svg_image(matrix=pymupdf.Identity, text_as_path=True)
        has_text = bool(page.get_text().strip())
        width_pt, height_pt = page.rect.width, page.rect.height

    root = etree.fromstring(svg_text.encode("utf-8"))
    root.set("width", f"{width_pt:.4f}pt")
    root.set("height", f"{height_pt:.4f}pt")
    if not root.get("viewBox"):
        root.set("viewBox", f"0 0 {width_pt:.4f} {height_pt:.4f}")
    return etree.tostring(root, encoding="unicode"), has_text


def _open(path: Path):
    with open(path, "rb") as handle:
        head = handle.read(1024)
    if b"%PDF-" not in head:
        if path.suffix.lower() == ".ai":
            raise ImportProblem(AI_NOT_PDF)
        raise ImportProblem("This PDF can't be read.")
    try:
        return pymupdf.open(path, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several exception types for damaged files
        raise ImportProblem("This PDF can't be read.") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_pdf_import.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\pdf_import.py tests\test_pdf_import.py
git commit -m "feat: import PDF and PDF-compatible AI pages via PyMuPDF" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Artwork loader

**Files:**
- Create: `src/rosetta/loader.py`
- Test: `tests/test_loader.py`

- [ ] **Step 1: Write the failing test**

```python
import pymupdf
import pytest

from rosetta.errors import ImportProblem
from rosetta.loader import load_artwork
from tests import samples


def test_loads_svg(tmp_path):
    path = tmp_path / "logo.svg"
    path.write_bytes(samples.ILLUSTRATOR_EXPORT)
    art = load_artwork(path)
    assert art.name == "logo"
    assert (art.width_mm, art.height_mm) == pytest.approx((200, 100), abs=0.001)
    assert art.source == "illustrator"
    assert {issue.code for issue in art.issues} == {"fill_only"}
    assert len(art.shapes) == 2


def test_loads_pdf_with_text_issue(tmp_path):
    path = tmp_path / "page.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    page.draw_line((10, 10), (150, 10), color=(0, 0, 0))
    page.insert_text((10, 100), "Hi")
    doc.save(path)
    doc.close()
    art = load_artwork(path)
    assert art.source == "pdf"
    assert "pdf_text" in {issue.code for issue in art.issues}


def test_affinity_native_file_is_explained(tmp_path):
    path = tmp_path / "drawing.afdesign"
    path.write_bytes(b"not really")
    with pytest.raises(ImportProblem, match="File › Export"):
        load_artwork(path)


def test_unsupported_extension_is_explained(tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(b"x")
    with pytest.raises(ImportProblem, match="SVG, PDF, or AI"):
        load_artwork(path)


def test_missing_file_is_explained(tmp_path):
    with pytest.raises(ImportProblem, match="can't be found"):
        load_artwork(tmp_path / "gone.svg")


def test_file_with_nothing_drawable_is_refused(tmp_path):
    path = tmp_path / "blank.svg"
    path.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"/>')
    with pytest.raises(ImportProblem, match="no lines to draw"):
        load_artwork(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.loader'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/loader.py`:
```python
"""Open an artwork file (SVG, PDF, or PDF-compatible AI) and turn it into plottable shapes."""
from dataclasses import dataclass
from pathlib import Path

from rosetta.errors import ImportProblem
from rosetta.flatten import Shape, flatten
from rosetta.issues import Issue, pdf_text_issue, scan_document, scan_shapes
from rosetta.pdf_import import pdf_page_to_svg
from rosetta.svgdoc import normalize

SUPPORTED_EXTENSIONS = (".svg", ".pdf", ".ai")
AFFINITY_EXTENSIONS = (".afdesign", ".afphoto", ".afpub", ".af")


@dataclass
class Artwork:
    name: str
    width_mm: float  # the document/artboard size, used as the piece's frame
    height_mm: float
    shapes: list[Shape]
    issues: list[Issue]
    source: str


def load_artwork(path: Path, page: int = 0) -> Artwork:
    path = Path(path)
    extension = path.suffix.lower()
    if extension in AFFINITY_EXTENSIONS:
        raise ImportProblem(
            "Affinity files can't be opened directly. In Affinity, use File › Export › "
            "SVG or PDF, then import that file."
        )
    if extension not in SUPPORTED_EXTENSIONS:
        raise ImportProblem(
            f"Rosetta Plotter can't open {extension or 'these'} files. Use SVG, PDF, or AI."
        )
    if not path.is_file():
        raise ImportProblem(f"The file {path.name} can't be found.")

    extra_issues = []
    if extension == ".svg":
        doc = normalize(path.read_bytes())
    else:
        svg_text, has_text = pdf_page_to_svg(path, page)
        doc = normalize(svg_text.encode("utf-8"), source_hint="pdf")
        if has_text:
            extra_issues.append(pdf_text_issue())

    issues = scan_document(doc.root, doc.source) + extra_issues
    shapes = flatten(doc)
    issues += scan_shapes(shapes)
    blocking = [issue for issue in issues if issue.blocking]
    if blocking:
        raise ImportProblem(blocking[0].message)
    return Artwork(path.stem, doc.width_mm, doc.height_mm, shapes, issues, doc.source)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_loader.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\loader.py tests\test_loader.py
git commit -m "feat: load SVG/PDF/AI artwork with problem checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Geometry (placement, bounds, intersection)

**Files:**
- Create: `src/rosetta/geometry.py`
- Test: `tests/test_geometry.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from rosetta.geometry import bbox, contains, intersect, place_point, rotated_size

# A 40 x 20 mm artwork. Its top-right corner is (40, 0).
W, H = 40.0, 20.0


def test_rotated_size():
    assert rotated_size(W, H, 0) == (W, H)
    assert rotated_size(W, H, 90) == (H, W)
    assert rotated_size(W, H, 180) == (W, H)
    assert rotated_size(W, H, -90) == (H, W)


def test_rotation_must_be_multiple_of_90():
    with pytest.raises(ValueError):
        rotated_size(W, H, 45)


@pytest.mark.parametrize(
    "rotation, expected",
    [
        (0, (40.0, 0.0)),    # top-right stays top-right
        (90, (20.0, 40.0)),  # clockwise: top-right -> bottom-right
        (180, (0.0, 20.0)),  # -> bottom-left
        (270, (0.0, 0.0)),   # -> top-left
    ],
)
def test_place_point_rotations_keep_art_in_its_box(rotation, expected):
    assert place_point((40.0, 0.0), W, H, 0, 0, 1.0, rotation, (0, 0)) == pytest.approx(expected)


def test_place_point_scale_offset_and_material_origin():
    # scale 2, placed at (5, 7) on paper whose corner is at (100, 50) on the bed
    assert place_point((10.0, 10.0), W, H, 5, 7, 2.0, 0, (100, 50)) == pytest.approx((125.0, 77.0))


def test_bbox_and_contains():
    assert bbox([[(1, 2), (5, 3)], [(0, 9)]]) == (0, 2, 5, 9)
    assert bbox([]) is None
    assert contains((0, 0, 10, 10), (10, 0))
    assert not contains((0, 0, 10, 10), (10.1, 0))


def test_intersect():
    assert intersect((0, 0, 10, 10), (5, 5, 20, 20)) == (5, 5, 10, 10)
    assert intersect((0, 0, 10, 10), (11, 11, 20, 20)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.geometry'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/geometry.py`:
```python
"""Pure geometry in millimetres.

Rect = (x0, y0, x1, y1) with x0 <= x1 and y0 <= y1. y grows downward on screen, which is
toward the student on the machine (spec §4). Rotation is clockwise as seen on screen.
"""
Point = tuple[float, float]
Rect = tuple[float, float, float, float]


def _rotation(rotation: int) -> int:
    normalized = rotation % 360
    if normalized not in (0, 90, 180, 270):
        raise ValueError("Rotation must be a multiple of 90 degrees.")
    return normalized


def rotated_size(width: float, height: float, rotation: int) -> tuple[float, float]:
    return (height, width) if _rotation(rotation) in (90, 270) else (width, height)


def place_point(
    point: Point,
    art_width: float,
    art_height: float,
    x: float,
    y: float,
    scale: float,
    rotation: int,
    origin: Point,
) -> Point:
    """Artwork point -> machine point. The rotated, scaled artwork box's top-left lands at
    origin + (x, y). origin is the material's corner nearest Home."""
    px, py = point
    turn = _rotation(rotation)
    if turn == 0:
        rx, ry = px, py
    elif turn == 90:
        rx, ry = art_height - py, px
    elif turn == 180:
        rx, ry = art_width - px, art_height - py
    else:
        rx, ry = py, art_width - px
    return (origin[0] + x + rx * scale, origin[1] + y + ry * scale)


def bbox(polylines) -> Rect | None:
    xs = [x for polyline in polylines for x, _ in polyline]
    ys = [y for polyline in polylines for _, y in polyline]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def contains(rect: Rect, point: Point, tolerance: float = 1e-6) -> bool:
    x0, y0, x1, y1 = rect
    x, y = point
    return x0 - tolerance <= x <= x1 + tolerance and y0 - tolerance <= y <= y1 + tolerance


def intersect(a: Rect, b: Rect) -> Rect | None:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x0 >= x1 or y0 >= y1:
        return None
    return (x0, y0, x1, y1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_geometry.py -v`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\geometry.py tests\test_geometry.py
git commit -m "feat: placement transform, bounds, rect intersection" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Polyline clipping

**Files:**
- Modify: `src/rosetta/geometry.py` (append functions)
- Test: `tests/test_clip.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from rosetta.geometry import clip_polyline

RECT = (0.0, 0.0, 10.0, 10.0)


def test_fully_inside_unchanged():
    line = [(1, 1), (5, 5), (9, 1)]
    assert clip_polyline(line, RECT) == [line]


def test_fully_outside_removed():
    assert clip_polyline([(11, 11), (20, 20)], RECT) == []


def test_crossing_out_and_back_in_splits_in_two():
    parts = clip_polyline([(5, 5), (15, 5), (15, 8), (5, 8)], RECT)
    assert len(parts) == 2
    assert parts[0] == pytest.approx([(5, 5), (10, 5)])
    assert parts[1] == pytest.approx([(10, 8), (5, 8)])


def test_segment_passing_through_is_trimmed_both_ends():
    parts = clip_polyline([(-5, 5), (15, 5)], RECT)
    assert parts == [pytest.approx([(0, 5), (10, 5)])]


def test_degenerate_input():
    assert clip_polyline([(1, 1)], RECT) == []
    assert clip_polyline([], RECT) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_clip.py -v`
Expected: FAIL with `ImportError: cannot import name 'clip_polyline'`

- [ ] **Step 3: Append the implementation to `src/rosetta/geometry.py`**

```python
_SAME = 1e-9


def _clip_segment(start: Point, end: Point, rect: Rect) -> tuple[Point, Point] | None:
    """Liang–Barsky: the part of segment start->end inside rect, or None."""
    x0, y0 = start
    dx, dy = end[0] - x0, end[1] - y0
    t_enter, t_exit = 0.0, 1.0
    for p, q in ((-dx, x0 - rect[0]), (dx, rect[2] - x0), (-dy, y0 - rect[1]), (dy, rect[3] - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            if t > t_exit:
                return None
            t_enter = max(t_enter, t)
        else:
            if t < t_enter:
                return None
            t_exit = min(t_exit, t)
    return (x0 + t_enter * dx, y0 + t_enter * dy), (x0 + t_exit * dx, y0 + t_exit * dy)


def _same(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= _SAME and abs(a[1] - b[1]) <= _SAME


def clip_polyline(points, rect: Rect) -> list[list[Point]]:
    """Split a polyline into the runs that lie inside rect."""
    runs: list[list[Point]] = []
    current: list[Point] = []
    for start, end in zip(points, points[1:]):
        piece = _clip_segment(start, end, rect)
        if piece is None:
            if len(current) >= 2:
                runs.append(current)
            current = []
            continue
        clipped_start, clipped_end = piece
        if current and _same(current[-1], clipped_start):
            current.append(clipped_end)
        else:
            if len(current) >= 2:
                runs.append(current)
            current = [clipped_start, clipped_end]
        if not _same(clipped_end, end):  # the segment leaves the rect here
            runs.append(current)
            current = []
    if len(current) >= 2:
        runs.append(current)
    return runs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_clip.py tests\test_geometry.py -v`
Expected: `14 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\geometry.py tests\test_clip.py
git commit -m "feat: clip polylines to a rectangle" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Compose a job (material, placement, color groups)

**Files:**
- Create: `src/rosetta/compose.py`
- Test: `tests/test_compose.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from rosetta.compose import (
    DEFAULT_MARGIN_MM, ColorGroup, Material, PlacedPiece, Placement, compose_job, initial_placement,
)
from rosetta.flatten import Shape
from rosetta.loader import Artwork
from rosetta.models import get_model

A4_MACHINE = get_model(1)  # 299.974 x 217.932 mm


def _art(width, height, shapes):
    return Artwork("art", width, height, shapes, [], "svg")


def _line(color, *points, stroked=True):
    return Shape((tuple(points),), color, stroked, not stroked)


def test_groups_by_color_in_first_appearance_order():
    art = _art(100, 100, [
        _line("#ff0000", (0, 0), (10, 0)),
        _line("#000000", (0, 5), (10, 5)),
        _line("#ff0000", (0, 9), (10, 9)),
    ])
    job = compose_job(A4_MACHINE, Material(0, 0, 200, 200), [PlacedPiece(art, Placement())])
    assert [group.color for group in job.groups] == ["#ff0000", "#000000"]
    assert len(job.groups[0].polylines) == 2
    assert job.groups[0].name == "red"


def test_material_offset_and_placement_applied():
    art = _art(10, 10, [_line("#000000", (0, 0), (10, 0))])
    job = compose_job(A4_MACHINE, Material(20, 30, 100, 100),
                      [PlacedPiece(art, Placement(x=5, y=5, scale=2.0))])
    assert job.groups[0].polylines[0] == pytest.approx([(25, 35), (45, 35)])
    assert job.ink_bbox == pytest.approx((25, 35, 45, 35))
    assert job.clipped is False


def test_clipped_to_paper_and_flagged():
    art = _art(100, 10, [_line("#000000", (0, 0), (100, 0))])
    job = compose_job(A4_MACHINE, Material(0, 0, 50, 50), [PlacedPiece(art, Placement(x=0, y=1))])
    assert job.groups[0].polylines[0] == pytest.approx([(0, 1), (50, 1)])
    assert job.clipped is True


def test_clipped_to_machine_reach():
    art = _art(10, 10, [_line("#000000", (0, 0), (10, 0))])
    # Paper hangs past the A4 machine's 299.974 mm reach.
    job = compose_job(A4_MACHINE, Material(295, 0, 50, 50), [PlacedPiece(art, Placement(x=0, y=1))])
    assert job.groups[0].polylines[0][-1][0] == pytest.approx(299.974)
    assert job.clipped is True


def test_white_skipped_by_default_but_can_be_kept():
    art = _art(10, 10, [_line("#ffffff", (0, 0), (10, 0))])
    pieces = [PlacedPiece(art, Placement())]
    assert compose_job(A4_MACHINE, Material(0, 0, 50, 50), pieces).groups == []
    assert len(compose_job(A4_MACHINE, Material(0, 0, 50, 50), pieces, skip_white=False).groups) == 1


def test_initial_placement_matching_paper_goes_to_corner():
    art = _art(215.9, 279.4, [])
    assert initial_placement(art, Material(0, 0, 216, 279)) == Placement(0, 0, 1.0, 0)


def test_initial_placement_centers_and_shrinks_to_fit():
    art = _art(400, 100, [])
    paper = Material(0, 0, 200, 200)
    placement = initial_placement(art, paper)
    usable = 200 - 2 * DEFAULT_MARGIN_MM
    assert placement.scale == pytest.approx(usable / 400)
    assert placement.x == pytest.approx(DEFAULT_MARGIN_MM)
    assert placement.y == pytest.approx((200 - 100 * placement.scale) / 2)


def test_initial_placement_small_art_keeps_size_and_centers():
    placement = initial_placement(_art(50, 20, []), Material(0, 0, 200, 100))
    assert placement == Placement(75, 40, 1.0, 0)


def test_color_group_defaults():
    assert ColorGroup("#0000ff").polylines == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_compose.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.compose'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/compose.py`:
```python
"""Put artwork on paper: placement, clipping to paper and machine reach, grouping by pen color."""
from dataclasses import dataclass, field

from rosetta.colors import WHITE, color_name
from rosetta.geometry import Point, Rect, bbox, clip_polyline, contains, intersect, place_point
from rosetta.loader import Artwork
from rosetta.models import MachineModel

DEFAULT_MARGIN_MM = 6.35  # 0.25 in
SAME_SIZE_TOLERANCE_MM = 1.0


@dataclass(frozen=True)
class Material:
    """Paper on the bed. (x, y) is its corner nearest Home, in machine mm."""

    x: float
    y: float
    width: float
    height: float

    @property
    def rect(self) -> Rect:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


@dataclass
class Placement:
    """Where a piece sits on the paper: its rotated, scaled box's top-left at (x, y)."""

    x: float = 0.0
    y: float = 0.0
    scale: float = 1.0
    rotation: int = 0  # clockwise degrees, multiple of 90


@dataclass
class PlacedPiece:
    artwork: Artwork
    placement: Placement


@dataclass
class ColorGroup:
    color: str
    polylines: list[list[Point]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return color_name(self.color)


@dataclass
class Job:
    groups: list[ColorGroup]  # plot order; layer number = index + 1
    ink_bbox: Rect | None  # bounds of everything that will be drawn (for Trace outline)
    clipped: bool  # True if anything was cut off at the paper edge or machine reach


def compose_job(
    model: MachineModel,
    material: Material,
    pieces: list[PlacedPiece],
    skip_white: bool = True,
) -> Job:
    travel_x, travel_y = model.travel_mm
    clip_rect = intersect(material.rect, (0.0, 0.0, travel_x, travel_y))
    groups: dict[str, ColorGroup] = {}
    clipped = False
    for piece in pieces:
        art, placement = piece.artwork, piece.placement
        for shape in art.shapes:
            if skip_white and shape.color == WHITE:
                continue
            for polyline in shape.polylines:
                placed = [
                    place_point(
                        point, art.width_mm, art.height_mm, placement.x, placement.y,
                        placement.scale, placement.rotation, (material.x, material.y),
                    )
                    for point in polyline
                ]
                if clip_rect is None:
                    clipped = True
                    continue
                if not all(contains(clip_rect, point) for point in placed):
                    clipped = True
                parts = clip_polyline(placed, clip_rect)
                if parts:
                    groups.setdefault(shape.color, ColorGroup(shape.color)).polylines.extend(parts)
    kept = [group for group in groups.values() if group.polylines]
    return Job(kept, bbox([line for group in kept for line in group.polylines]), clipped)


def initial_placement(
    artwork: Artwork, material: Material, margin: float = DEFAULT_MARGIN_MM
) -> Placement:
    """Where a newly imported piece lands (spec §5, step 3).

    Artwork drawn at the paper's size lands exactly on the paper. Anything else is
    centered and shrunk, never enlarged, to fit inside the margins.
    """
    if (
        abs(artwork.width_mm - material.width) <= SAME_SIZE_TOLERANCE_MM
        and abs(artwork.height_mm - material.height) <= SAME_SIZE_TOLERANCE_MM
    ):
        return Placement(0.0, 0.0, 1.0, 0)
    usable_width = max(material.width - 2 * margin, 1.0)
    usable_height = max(material.height - 2 * margin, 1.0)
    scale = min(1.0, usable_width / artwork.width_mm, usable_height / artwork.height_mm)
    width, height = artwork.width_mm * scale, artwork.height_mm * scale
    return Placement((material.width - width) / 2, (material.height - height) / 2, scale, 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_compose.py -v`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\compose.py tests\test_compose.py
git commit -m "feat: compose placed artwork into clipped pen-color groups" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Plot-ready SVG

**Files:**
- Create: `src/rosetta/plotsvg.py`
- Test: `tests/test_plotsvg.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from lxml import etree

from rosetta.compose import ColorGroup
from rosetta.flatten import flatten
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg
from rosetta.svgdoc import INKSCAPE_NS, normalize

GROUPS = [
    ColorGroup("#ff0000", [[(10.0, 10.0), (110.0, 10.0)]]),
    ColorGroup("#000000", [[(20.0, 20.0), (20.0, 120.0), (60.0, 120.0)]]),
]


def test_page_is_machine_travel_in_mm():
    root = etree.fromstring(plot_svg(get_model(5), GROUPS).encode())
    assert root.get("width") == "864.1080mm"
    assert root.get("height") == "594.1060mm"
    assert root.get("viewBox") == "0 0 864.1080 594.1060"


def test_one_numbered_layer_per_color():
    root = etree.fromstring(plot_svg(get_model(1), GROUPS).encode())
    labels = [g.get(f"{{{INKSCAPE_NS}}}label") for g in root]
    modes = {g.get(f"{{{INKSCAPE_NS}}}groupmode") for g in root}
    assert labels == ["1", "2"]
    assert modes == {"layer"}


def test_no_xml_declaration():
    assert not plot_svg(get_model(1), GROUPS).startswith("<?xml")


def test_round_trip_through_ems_parser():
    shapes = flatten(normalize(plot_svg(get_model(1), GROUPS).encode()))
    assert [shape.color for shape in shapes] == ["#ff0000", "#000000"]
    assert shapes[1].polylines[0] == pytest.approx(((20, 20), (20, 120), (60, 120)), abs=0.001)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_plotsvg.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.plotsvg'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/plotsvg.py`:
```python
"""Write the plot-ready SVG the EMS engine plots (spec §6.2 step 8).

Page = the machine's reachable area in mm, so SVG coordinates are machine coordinates.
One Inkscape layer per pen color, numbered from 1, so each color plots as its own
'layers'-mode run with a pen change in between. No XML declaration, so the text can be
passed straight to pyaxidraw's plot_setup().
"""
from lxml import etree

from rosetta.compose import ColorGroup
from rosetta.models import MachineModel
from rosetta.svgdoc import INKSCAPE_NS, SVG_NS


def plot_svg(model: MachineModel, groups: list[ColorGroup]) -> str:
    travel_x, travel_y = model.travel_mm
    root = etree.Element(f"{{{SVG_NS}}}svg", nsmap={None: SVG_NS, "inkscape": INKSCAPE_NS})
    root.set("width", f"{travel_x:.4f}mm")
    root.set("height", f"{travel_y:.4f}mm")
    root.set("viewBox", f"0 0 {travel_x:.4f} {travel_y:.4f}")
    for number, group in enumerate(groups, start=1):
        layer = etree.SubElement(root, f"{{{SVG_NS}}}g")
        layer.set(f"{{{INKSCAPE_NS}}}groupmode", "layer")
        layer.set(f"{{{INKSCAPE_NS}}}label", str(number))
        for polyline in group.polylines:
            element = etree.SubElement(layer, f"{{{SVG_NS}}}polyline")
            element.set("points", " ".join(f"{x:.4f},{y:.4f}" for x, y in polyline))
            element.set("style", f"fill:none;stroke:{group.color}")
    return etree.tostring(root, encoding="unicode")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_plotsvg.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\plotsvg.py tests\test_plotsvg.py
git commit -m "feat: emit plot-ready SVG with one layer per pen color" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Engine settings and plotter identity

**Files:**
- Create: `src/rosetta/engine/options.py`, `src/rosetta/engine/identity.py`
- Test: `tests/test_engine_options.py`, `tests/test_identity.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_engine_options.py`:
```python
from types import SimpleNamespace

import pytest

from rosetta.engine.options import PlotSettings, apply_settings


def test_pen_up_follows_pen_down():
    assert PlotSettings(model=1, pen_down=30).pen_up == 60
    assert PlotSettings(model=1, pen_down=55).pen_up == 75
    assert PlotSettings(model=1, pen_down=95).pen_up == 100


def test_apply_settings_sets_ems_options():
    ad = SimpleNamespace(options=SimpleNamespace())
    apply_settings(ad, PlotSettings(model=5, penlift=3, pen_down=40, pen_type="brush"))
    o = ad.options
    assert (o.model, o.penlift) == (5, 3)
    assert (o.pen_pos_down, o.pen_pos_up) == (40, 60)
    assert (o.speed_pendown, o.speed_penup) == (12, 75)
    assert o.auto_rotate is False
    assert (o.reordering, o.hiding) == (2, False)


def test_apply_settings_rejects_unknown_values():
    ad = SimpleNamespace(options=SimpleNamespace())
    with pytest.raises(ValueError):
        apply_settings(ad, PlotSettings(model=9))
    with pytest.raises(ValueError):
        apply_settings(ad, PlotSettings(model=1, pen_type="crayon"))
```

`tests/test_identity.py`:
```python
from rosetta.engine.identity import NICKNAME_MAX, Identity, decode_nickname, encode_nickname


def test_encode_fits_in_16_characters():
    assert encode_nickname(Identity(2, 1, "PSU Lab A")) == "PSU Lab A m2p1"
    long_name = encode_nickname(Identity(5, 3, "Portland State Architecture"))
    assert len(long_name) <= NICKNAME_MAX
    assert long_name.endswith(" m5p3")


def test_encode_without_label():
    assert encode_nickname(Identity(6, 1, "")) == "m6p1"


def test_decode_round_trip():
    for identity in (Identity(2, 1, "PSU Lab A"), Identity(6, 1, "")):
        assert decode_nickname(encode_nickname(identity)) == identity


def test_decode_foreign_nickname_is_none():
    assert decode_nickname("Jen's AxiDraw") is None
    assert decode_nickname("") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests\test_engine_options.py tests\test_identity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.engine.options'`

- [ ] **Step 3: Write the implementations**

`src/rosetta/engine/options.py`:
```python
"""Rosetta's plot settings, and how they map onto EMS pyaxidraw options."""
from dataclasses import dataclass

from rosetta.models import MODELS, PEN_TYPES, PEN_UP_SPEED


@dataclass
class PlotSettings:
    model: int  # EMS model number (rosetta.models.MODELS)
    penlift: int = 1  # EMS penlift: 1 default for model, 2 standard servo, 3 brushless
    pen_down: int = 30  # pen-down height, percent
    pen_type: str = "fineliner"  # key into rosetta.models.PEN_TYPES
    reordering: int = 2  # EMS: reorder and allow reversal
    hiding: bool = False  # EMS hidden-line removal (Advanced only)

    @property
    def pen_up(self) -> int:
        return min(100, max(60, self.pen_down + 20))


def apply_settings(ad, settings: PlotSettings) -> None:
    """Set EMS options. Call after ad.plot_setup() or ad.interactive()."""
    if settings.model not in MODELS:
        raise ValueError(f"Unknown AxiDraw model number: {settings.model}")
    if settings.pen_type not in PEN_TYPES:
        raise ValueError(f"Unknown pen type: {settings.pen_type}")
    options = ad.options
    options.model = settings.model
    options.penlift = settings.penlift
    options.pen_pos_down = settings.pen_down
    options.pen_pos_up = settings.pen_up
    options.speed_pendown = PEN_TYPES[settings.pen_type].speed_pendown
    options.speed_penup = PEN_UP_SPEED
    options.auto_rotate = False  # spec §4: never rotate; screen = paper
    options.reordering = settings.reordering
    options.hiding = settings.hiding


def make_axidraw():
    """A fresh EMS AxiDraw object. Imported lazily so non-engine code loads fast."""
    from pyaxidraw import axidraw

    return axidraw.AxiDraw()
```

`src/rosetta/engine/identity.py`:
```python
"""The plotter's model, stored in its EBB nickname so every laptop recognizes it (spec §8)."""
import re
from dataclasses import dataclass

NICKNAME_MAX = 16  # EBB nickname limit
_SUFFIX = re.compile(r"(?:^|\s)m([1-7])p([1-3])$")


@dataclass(frozen=True)
class Identity:
    model: int
    penlift: int
    label: str


def encode_nickname(identity: Identity) -> str:
    suffix = f"m{identity.model}p{identity.penlift}"
    room = NICKNAME_MAX - len(suffix) - 1
    label = identity.label.strip()[:room].strip() if room > 0 else ""
    return f"{label} {suffix}" if label else suffix


def decode_nickname(nickname: str) -> Identity | None:
    text = (nickname or "").strip()
    match = _SUFFIX.search(text)
    if not match:
        return None
    return Identity(int(match.group(1)), int(match.group(2)), text[: match.start()].strip())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests\test_engine_options.py tests\test_identity.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\engine\options.py src\rosetta\engine\identity.py tests\test_engine_options.py tests\test_identity.py
git commit -m "feat: EMS option mapping and plotter identity nickname" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: Plot runner (estimate, progress, pause, resume)

These tests run the real EMS engine in preview mode. No plotter is needed.

**Files:**
- Create: `src/rosetta/engine/awake.py`, `src/rosetta/engine/runner.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from rosetta.compose import ColorGroup
from rosetta.engine.awake import keep_awake
from rosetta.engine.options import PlotSettings
from rosetta.engine.runner import (
    PlotOutcome, PlotRunner, Progress, estimate, outcome_for_code, set_resume_origin_home,
)
from rosetta.models import get_model
from rosetta.plotsvg import plot_svg

SETTINGS = PlotSettings(model=1)


def _square_plot() -> str:
    square = [(10.0, 10.0), (110.0, 10.0), (110.0, 110.0), (10.0, 110.0), (10.0, 10.0)]
    return plot_svg(get_model(1), [ColorGroup("#000000", [square])])


class AlwaysSet:
    """Stands in for threading.Event: a pause that's already been requested."""

    def set(self):
        pass

    def is_set(self):
        return True


def test_outcome_codes():
    assert outcome_for_code(0) is PlotOutcome.COMPLETED
    assert outcome_for_code(101) is PlotOutcome.NOT_CONNECTED
    assert outcome_for_code(102) is PlotOutcome.PAUSED
    assert outcome_for_code(103) is PlotOutcome.PAUSED
    assert outcome_for_code(104) is PlotOutcome.DISCONNECTED
    assert outcome_for_code(999) is PlotOutcome.ERROR


def test_estimate_square():
    result = estimate(_square_plot(), 1, SETTINGS)
    assert result.seconds > 1
    assert result.pendown_m == pytest.approx(0.4, abs=0.01)


def test_preview_run_completes():
    progress = []
    result = PlotRunner(poll_interval=0.001).run(
        _square_plot(), 1, SETTINGS, on_progress=progress.append, preview=True
    )
    assert result.outcome is PlotOutcome.COMPLETED
    assert result.resume_svg is None
    assert all(isinstance(item, Progress) for item in progress)


def test_pause_then_resume():
    paused = PlotRunner(event_factory=AlwaysSet).run(_square_plot(), 1, SETTINGS, preview=True)
    assert paused.outcome is PlotOutcome.PAUSED
    assert "plotdata" in paused.resume_svg
    resumed = PlotRunner().run(paused.resume_svg, 1, SETTINGS, resume=True, preview=True)
    assert resumed.outcome is PlotOutcome.COMPLETED


def test_set_resume_origin_home():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><plotdata last_x="12.5" last_y="4.0"/></svg>'
    updated = set_resume_origin_home(svg)
    assert 'last_x="0"' in updated and 'last_y="0"' in updated


def test_set_resume_origin_home_without_data():
    with pytest.raises(ValueError):
        set_resume_origin_home('<svg xmlns="http://www.w3.org/2000/svg"/>')


def test_keep_awake_enters_and_exits():
    with keep_awake():
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.engine.awake'`

- [ ] **Step 3: Write `src/rosetta/engine/awake.py`**

```python
"""Keep Windows from sleeping while the current thread is plotting."""
import contextlib
import ctypes
import sys

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


@contextlib.contextmanager
def keep_awake():
    if sys.platform != "win32":
        yield
        return
    kernel32 = ctypes.windll.kernel32
    kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        yield
    finally:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)
```

- [ ] **Step 4: Write `src/rosetta/engine/runner.py`**

```python
"""Run plots and time estimates through the EMS engine.

Each run uses a fresh EMS AxiDraw object in 'layers' mode (one pen color per run).
Live position is read from EMS internals pinned by tests/test_engine_contract.py.
"""
import threading
from dataclasses import dataclass
from enum import Enum

from lxml import etree

from rosetta.engine.awake import keep_awake
from rosetta.engine.options import PlotSettings, apply_settings, make_axidraw
from rosetta.units import MM_PER_INCH


class PlotOutcome(Enum):
    COMPLETED = "completed"
    PAUSED = "paused"
    DISCONNECTED = "disconnected"
    NOT_CONNECTED = "not_connected"
    ERROR = "error"


# EMS plot_status.stopped after a run (see axidrawinternal/axidraw.py, pause_check).
_CODES = {
    0: PlotOutcome.COMPLETED,
    101: PlotOutcome.NOT_CONNECTED,
    102: PlotOutcome.PAUSED,  # physical pause button
    103: PlotOutcome.PAUSED,  # our software pause
    104: PlotOutcome.DISCONNECTED,
}

MESSAGES = {
    PlotOutcome.COMPLETED: "Plot finished.",
    PlotOutcome.PAUSED: "Plot paused.",
    PlotOutcome.DISCONNECTED: "Plotter disconnected. Plug it back in, slide the pen Home, then resume.",
    PlotOutcome.NOT_CONNECTED: "No plotter found. Plug in the USB cable and the power adapter.",
    PlotOutcome.ERROR: "The plot stopped unexpectedly.",
}


def outcome_for_code(code: int) -> PlotOutcome:
    return _CODES.get(code, PlotOutcome.ERROR)


@dataclass
class PlotResult:
    outcome: PlotOutcome
    resume_svg: str | None  # set when PAUSED or DISCONNECTED
    message: str


@dataclass(frozen=True)
class Progress:
    x_mm: float
    y_mm: float
    pendown_mm: float  # pen-down distance drawn so far in this run


@dataclass(frozen=True)
class Estimate:
    seconds: float
    pendown_m: float


def _clean(svg_text: str) -> str:
    """Drop an XML declaration so plot_setup() can parse the text as a string."""
    text = svg_text.lstrip()
    if text.startswith("<?xml"):
        text = text[text.index("?>") + 2:].lstrip()
    return text


def estimate(svg_text: str, layer: int, settings: PlotSettings, factory=make_axidraw) -> Estimate:
    ad = factory()
    ad.plot_setup(_clean(svg_text))
    apply_settings(ad, settings)
    ad.options.mode = "layers"
    ad.options.layer = layer
    ad.options.preview = True
    ad.options.rendering = 0
    ad.plot_run()
    stats = ad.plot_status.stats
    # down_travel_tot is only filled in when EMS prints its own report; use whichever is set.
    pendown_in = max(stats.down_travel_tot, stats.down_travel_inch)
    return Estimate(stats.pt_estimate / 1000.0, pendown_in * MM_PER_INCH / 1000.0)


class PlotRunner:
    def __init__(self, factory=make_axidraw, poll_interval: float = 0.1, event_factory=threading.Event):
        self._factory = factory
        self._poll_interval = poll_interval
        self._event_factory = event_factory
        self._pause = event_factory()

    def pause(self) -> None:
        """Ask the current run to pause. Safe to call from any thread."""
        self._pause.set()

    def run(
        self,
        svg_text: str,
        layer: int,
        settings: PlotSettings,
        on_progress=None,
        resume: bool = False,
        preview: bool = False,
    ) -> PlotResult:
        """Plot one layer (or resume a paused one). Blocks; call from a worker thread."""
        ad = self._factory()
        ad.plot_setup(_clean(svg_text))
        apply_settings(ad, settings)
        ad.options.preview = preview
        if resume:
            ad.options.mode = "res_plot"
        else:
            ad.options.mode = "layers"
            ad.options.layer = layer
        self._pause = self._event_factory()
        ad.set_up_pause_receiver(self._pause)

        done = threading.Event()
        poller = None
        if on_progress is not None:
            poller = threading.Thread(target=self._poll, args=(ad, on_progress, done), daemon=True)
            poller.start()
        try:
            with keep_awake():
                output = ad.plot_run(True)
        except Exception as exc:  # serial errors surface here; report, don't crash the app
            return PlotResult(PlotOutcome.ERROR, None, f"{MESSAGES[PlotOutcome.ERROR]} ({exc})")
        finally:
            done.set()
            if poller is not None:
                poller.join()

        outcome = outcome_for_code(ad.plot_status.stopped)
        keep_resume = outcome in (PlotOutcome.PAUSED, PlotOutcome.DISCONNECTED)
        return PlotResult(outcome, output if keep_resume else None, MESSAGES[outcome])

    def return_home(self, resume_svg: str, settings: PlotSettings) -> str:
        """After a pause, drive the pen back Home. Returns resume data that now starts from Home."""
        ad = self._factory()
        ad.plot_setup(_clean(resume_svg))
        apply_settings(ad, settings)
        ad.options.mode = "res_home"
        return ad.plot_run(True)

    def _poll(self, ad, on_progress, done: threading.Event) -> None:
        while not done.wait(self._poll_interval):
            on_progress(
                Progress(
                    (ad.pen.phys.xpos or 0.0) * MM_PER_INCH,
                    (ad.pen.phys.ypos or 0.0) * MM_PER_INCH,
                    ad.plot_status.stats.down_travel_inch * MM_PER_INCH,
                )
            )


def set_resume_origin_home(resume_svg: str) -> str:
    """After the student slides the pen back Home by hand, make the resume start from Home."""
    root = etree.fromstring(_clean(resume_svg).encode("utf-8"))
    nodes = root.xpath("//*[local-name()='plotdata']")
    if not nodes:
        raise ValueError("No resume data in this plot.")
    nodes[0].set("last_x", "0")
    nodes[0].set("last_y", "0")
    return etree.tostring(root, encoding="unicode")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_runner.py -v`
Expected: `7 passed`. If `test_pause_then_resume` fails because the outcome is COMPLETED, pyaxidraw 3.9.6's `plot_run` is replacing the pause receiver. In that case:
- Open `.venv\Lib\site-packages\pyaxidraw\axidraw.py` and find where `plot_run` sets `_software_pause_event`.
- Move the `ad.set_up_pause_receiver(self._pause)` call to wherever pyaxidraw's own setup finishes.
- Rerun. Report the change in the commit message.

- [ ] **Step 6: Commit**

```powershell
git add src\rosetta\engine\awake.py src\rosetta\engine\runner.py tests\test_runner.py
git commit -m "feat: plot runner with estimates, live progress, pause and resume" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 18: Interactive plotter control

Hardware commands are tested with a fake EMS object. The real plotter is exercised in Task 21.

**Files:**
- Create: `src/rosetta/engine/plotter.py`
- Test: `tests/test_plotter.py`

- [ ] **Step 1: Write the failing test**

```python
from types import SimpleNamespace

import pytest

from rosetta.engine import plotter as plotter_module
from rosetta.engine.identity import Identity
from rosetta.engine.options import PlotSettings
from rosetta.engine.plotter import Plotter


class FakeAD:
    def __init__(self, connect_ok=True):
        self.calls = []
        self.options = SimpleNamespace()
        self.plot_status = SimpleNamespace(port="COM9")
        self._connect_ok = connect_ok
        self._pos = (0.0, 0.0)

    def interactive(self):
        self.calls.append(("interactive",))

    def connect(self):
        self.calls.append(("connect",))
        self._pos = (0.0, 0.0)
        return self._connect_ok

    def disconnect(self):
        self.calls.append(("disconnect",))

    def moveto(self, x, y):
        self.calls.append(("moveto", round(x, 3), round(y, 3)))
        self._pos = (x, y)

    def lineto(self, x, y):
        self.calls.append(("lineto", round(x, 3), round(y, 3)))
        self._pos = (x, y)

    def penup(self):
        self.calls.append(("penup",))

    def pendown(self):
        self.calls.append(("pendown",))

    def update(self):
        self.calls.append(("update",))

    def turtle_pos(self):
        return self._pos


@pytest.fixture
def fake_ebb(monkeypatch):
    log = []
    ebb_motion = SimpleNamespace(
        queryVoltage=lambda port, verbose=True: True,
        sendDisableMotors=lambda port, verbose=True: log.append(("motors_off", port)),
    )
    ebb_serial = SimpleNamespace(
        queryVersion=lambda port: "EBBv13_and_above EB Firmware Version 2.8.1\r\n",
        query_nickname=lambda port, verbose=True: "PSU Lab A m5p1",
        min_version=lambda port, version: True,
        write_nickname=lambda port, name: log.append(("write", name)) or True,
        reboot=lambda port: log.append(("reboot", port)),
    )
    monkeypatch.setattr(plotter_module, "ebb_motion", ebb_motion)
    monkeypatch.setattr(plotter_module, "ebb_serial", ebb_serial)
    return log


def _connected(model=1):
    fakes = []

    def factory():
        fakes.append(FakeAD())
        return fakes[-1]

    plotter = Plotter(factory=factory)
    assert plotter.connect(PlotSettings(model=model))
    return plotter, fakes


def test_connect_uses_mm_and_settings():
    plotter, fakes = _connected(model=5)
    assert fakes[0].options.units == 2
    assert fakes[0].options.model == 5
    assert fakes[0].calls[:2] == [("interactive",), ("connect",)]


def test_connect_failure_returns_false():
    plotter = Plotter(factory=lambda: FakeAD(connect_ok=False))
    assert plotter.connect(PlotSettings(model=1)) is False
    assert plotter.connected is False


def test_status_queries(fake_ebb):
    plotter, _ = _connected()
    assert plotter.firmware() == "EBBv13_and_above EB Firmware Version 2.8.1"
    assert plotter.power_ok() is True
    assert plotter.read_identity() == Identity(5, 1, "PSU Lab A")


def test_write_identity_reboots_and_drops_session(fake_ebb):
    plotter, _ = _connected()
    assert plotter.write_identity(Identity(2, 1, "PSU Lab A")) is True
    assert ("write", "PSU Lab A m2p1") in fake_ebb
    assert ("reboot", "COM9") in fake_ebb
    assert plotter.connected is False


def test_motors_off_lifts_pen_first(fake_ebb):
    plotter, fakes = _connected()
    plotter.motors_off()
    assert fakes[0].calls[-1] == ("penup",)
    assert fake_ebb[-1] == ("motors_off", "COM9")


def test_set_home_reconnects():
    plotter, fakes = _connected()
    plotter.set_home()
    assert len(fakes) == 2
    assert ("disconnect",) in fakes[0].calls
    assert plotter.connected


def test_goto_and_jog_stay_within_reach():
    plotter, fakes = _connected(model=1)  # 299.974 x 217.932
    plotter.goto(500, -10)
    assert fakes[0].calls[-1] == ("moveto", 299.974, 0.0)
    plotter.goto(10, 10)
    plotter.jog(5, -20)
    assert fakes[0].calls[-1] == ("moveto", 15.0, 0.0)


def test_pen_height_updates_live_when_pen_is_down():
    plotter, fakes = _connected()
    plotter.pen_down()
    plotter.set_pen_down_height(45)
    assert fakes[0].options.pen_pos_down == 45
    assert fakes[0].options.pen_pos_up == 65
    assert fakes[0].calls[-3:] == [("update",), ("penup",), ("pendown",)]


def test_trace_goes_around_rect_and_home():
    plotter, fakes = _connected()
    plotter.trace((10, 20, 30, 40))
    moves = [call for call in fakes[0].calls if call[0] == "moveto"]
    assert moves == [
        ("moveto", 10, 20), ("moveto", 30, 20), ("moveto", 30, 40),
        ("moveto", 10, 40), ("moveto", 10, 20), ("moveto", 0, 0),
    ]


def test_test_mark_draws_10mm_line_near_corner():
    plotter, fakes = _connected()
    plotter.test_mark(50, 60)
    assert ("lineto", 65, 65) in fakes[0].calls
    assert fakes[0].calls[-1] == ("moveto", 0, 0)


def test_release_for_plot_goes_home_then_disconnects():
    plotter, fakes = _connected()
    plotter.goto(100, 100)
    plotter.release_for_plot()
    assert fakes[0].calls[-2:] == [("moveto", 0, 0), ("disconnect",)]
    assert plotter.connected is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_plotter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.engine.plotter'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/engine/plotter.py`:
```python
"""Interactive control of a connected plotter: home, jog, pen height, trace, identity.

Uses the EMS interactive context. EMS assumes the pen is at Home (0, 0) when connect()
succeeds, so set_home() reconnects, and release_for_plot() returns Home before a plot
run takes over (spec §6.1).
"""
from plotink import ebb_motion, ebb_serial

from rosetta.engine.identity import Identity, decode_nickname, encode_nickname
from rosetta.engine.options import PlotSettings, apply_settings, make_axidraw
from rosetta.models import get_model

MIN_FIRMWARE_FOR_NICKNAME = "2.5.5"
EMS_UNITS_MM = 2


class Plotter:
    def __init__(self, factory=make_axidraw):
        self._factory = factory
        self._ad = None
        self._settings: PlotSettings | None = None
        self._pen_is_down = False

    @property
    def connected(self) -> bool:
        return self._ad is not None

    def connect(self, settings: PlotSettings) -> bool:
        ad = self._factory()
        ad.interactive()
        apply_settings(ad, settings)
        ad.options.units = EMS_UNITS_MM
        if not ad.connect():
            return False
        self._ad, self._settings, self._pen_is_down = ad, settings, False
        return True

    def disconnect(self) -> None:
        if self._ad is not None:
            try:
                self._ad.disconnect()
            finally:
                self._ad = None

    def firmware(self) -> str:
        return ebb_serial.queryVersion(self._port()).strip()

    def power_ok(self) -> bool:
        return bool(ebb_motion.queryVoltage(self._port(), False))

    def read_identity(self) -> Identity | None:
        nickname = ebb_serial.query_nickname(self._port(), False)
        return decode_nickname(nickname) if nickname else None

    def write_identity(self, identity: Identity) -> bool:
        """Store the model on the plotter. The board reboots, so this session ends."""
        port = self._port()
        if not ebb_serial.min_version(port, MIN_FIRMWARE_FOR_NICKNAME):
            return False
        written = bool(ebb_serial.write_nickname(port, encode_nickname(identity)))
        if written:
            ebb_serial.reboot(port)
        self._ad = None
        return written

    def motors_off(self) -> None:
        self.pen_up()
        ebb_motion.sendDisableMotors(self._port(), False)

    def set_home(self) -> None:
        """The student has slid the pen to Home: reconnect so EMS treats here as (0, 0)."""
        settings = self._settings
        self.disconnect()
        if not self.connect(settings):
            raise RuntimeError("Lost the plotter while setting Home.")

    def position(self) -> tuple[float, float]:
        x, y = self._require().turtle_pos()
        return (x, y)

    def goto(self, x: float, y: float) -> None:
        travel_x, travel_y = get_model(self._settings.model).travel_mm
        self._require().moveto(min(max(x, 0.0), travel_x), min(max(y, 0.0), travel_y))

    def jog(self, dx: float, dy: float) -> None:
        x, y = self.position()
        self.goto(x + dx, y + dy)

    def pen_up(self) -> None:
        self._require().penup()
        self._pen_is_down = False

    def pen_down(self) -> None:
        self._require().pendown()
        self._pen_is_down = True

    def set_pen_down_height(self, percent: int) -> None:
        ad = self._require()
        self._settings.pen_down = percent
        ad.options.pen_pos_down = percent
        ad.options.pen_pos_up = self._settings.pen_up
        ad.update()
        if self._pen_is_down:  # re-lower so the new height shows on the real pen
            ad.penup()
            ad.pendown()

    def trace(self, rect: tuple[float, float, float, float]) -> None:
        """Pen up: go around rect so the student sees where the drawing lands, then Home."""
        x0, y0, x1, y1 = rect
        self.pen_up()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)):
            self.goto(x, y)
        self.goto(0.0, 0.0)

    def test_mark(self, corner_x: float, corner_y: float) -> None:
        """A 10 mm line just inside the paper corner nearest Home, then back Home."""
        self.pen_up()
        self.goto(corner_x + 5, corner_y + 5)
        self._require().lineto(corner_x + 15, corner_y + 5)
        self._pen_is_down = True
        self.pen_up()
        self.goto(0.0, 0.0)

    def release_for_plot(self) -> None:
        """Return Home and let go of the USB port so a plot run can take over."""
        self.pen_up()
        self.goto(0.0, 0.0)
        self.disconnect()

    def _require(self):
        if self._ad is None:
            raise RuntimeError("Not connected to a plotter.")
        return self._ad

    def _port(self):
        return self._require().plot_status.port
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_plotter.py -v`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```powershell
git add src\rosetta\engine\plotter.py tests\test_plotter.py
git commit -m "feat: interactive plotter control (home, jog, pen height, trace, identity)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 19: `rosetta-plot` command line

**Files:**
- Create: `src/rosetta/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from rosetta.cli import format_duration, main
from tests import samples


def test_format_duration():
    assert format_duration(45) == "45 s"
    assert format_duration(200) == "3 min 20 s"
    assert format_duration(3720) == "1 h 02 min"


def _job(tmp_path):
    (tmp_path / "art.svg").write_bytes(samples.INKSCAPE_MM)
    job = {
        "model": 1,
        "material": {"x": 0, "y": 0, "width": 215.9, "height": 279.4},
        "pieces": [{"path": "art.svg"}],
    }
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    return job_path


def test_prepare_writes_svg_and_sidecar(tmp_path, capsys):
    out = tmp_path / "out" / "plot"
    assert main(["prepare", str(_job(tmp_path)), "-o", str(out)]) == 0
    svg = out.with_suffix(".svg").read_text(encoding="utf-8")
    meta = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert 'inkscape:label="1"' in svg
    assert meta["model"] == 1
    assert meta["layers"] == [{"layer": 1, "color": "#000000", "name": "black"}]
    assert len(meta["ink_bbox"]) == 4
    assert "1 pen color" in capsys.readouterr().out


def test_estimate_prints_per_layer_and_total(tmp_path, capsys):
    out = tmp_path / "plot"
    main(["prepare", str(_job(tmp_path)), "-o", str(out)])
    capsys.readouterr()
    assert main(["estimate", str(out.with_suffix(".svg"))]) == 0
    text = capsys.readouterr().out
    assert "Layer 1 (black)" in text
    assert "Total:" in text


def test_import_problem_is_reported_not_raised(tmp_path, capsys):
    job = {"model": 1, "material": {"width": 100, "height": 100}, "pieces": [{"path": "missing.svg"}]}
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    assert main(["prepare", str(job_path), "-o", str(tmp_path / "plot")]) == 2
    assert "can't be found" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests\test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rosetta.cli'`

- [ ] **Step 3: Write the implementation**

`src/rosetta/cli.py`:
```python
"""rosetta-plot: command-line access to the Rosetta core, for testing on real plotters.

Students use the app (Plan 2). This tool exists so plots can be tested on hardware early.

    rosetta-plot prepare job.json -o out\\plot   -> out\\plot.svg + out\\plot.json
    rosetta-plot estimate out\\plot.svg
    rosetta-plot info
    rosetta-plot identify --model 5 --label "PSU Lab"
    rosetta-plot trace out\\plot.svg
    rosetta-plot plot out\\plot.svg --pen-down 30 --pen-type fineliner
"""
import argparse
import json
import threading
from pathlib import Path

from rosetta.compose import Material, PlacedPiece, Placement, compose_job, initial_placement
from rosetta.engine.identity import Identity
from rosetta.engine.options import PlotSettings
from rosetta.engine.plotter import Plotter
from rosetta.engine.runner import PlotOutcome, PlotRunner, estimate, set_resume_origin_home
from rosetta.errors import ImportProblem
from rosetta.loader import load_artwork
from rosetta.models import MODELS, PEN_TYPES, get_model
from rosetta.plotsvg import plot_svg

HOME_INSTRUCTION = "Slide the pen to the corner next to the HOME label and the USB port."


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {secs:02d} s"
    return f"{secs} s"


def cmd_prepare(args) -> int:
    job = json.loads(args.job.read_text(encoding="utf-8"))
    model = get_model(int(job["model"]))
    paper = job["material"]
    material = Material(
        float(paper.get("x", 0)), float(paper.get("y", 0)), float(paper["width"]), float(paper["height"])
    )
    pieces = []
    for spec in job["pieces"]:
        artwork = load_artwork((args.job.parent / spec["path"]).resolve(), int(spec.get("page", 0)))
        for issue in artwork.issues:
            print(f"  [{artwork.name}] {issue.message}")
        if any(key in spec for key in ("x", "y", "scale", "rotation")):
            placement = Placement(
                float(spec.get("x", 0)), float(spec.get("y", 0)),
                float(spec.get("scale", 1.0)), int(spec.get("rotation", 0)),
            )
        else:
            placement = initial_placement(artwork, material)
        pieces.append(PlacedPiece(artwork, placement))

    result = compose_job(model, material, pieces, skip_white=bool(job.get("skip_white", True)))
    if not result.groups:
        print("Nothing to plot: no lines land on the paper.")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".svg").write_text(plot_svg(model, result.groups), encoding="utf-8")
    meta = {
        "model": model.number,
        "layers": [
            {"layer": number, "color": group.color, "name": group.name}
            for number, group in enumerate(result.groups, start=1)
        ],
        "ink_bbox": list(result.ink_bbox),
        "clipped": result.clipped,
    }
    args.out.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    count = len(result.groups)
    print(f"Prepared {args.out.with_suffix('.svg')} with {count} pen color{'s' if count != 1 else ''}.")
    if result.clipped:
        print("  Some lines hang off the paper or out of reach; those parts won't be drawn.")
    return 0


def _read_plot(path: Path) -> tuple[str, dict]:
    svg = path.with_suffix(".svg").read_text(encoding="utf-8")
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    return svg, meta


def _settings(args, meta) -> PlotSettings:
    return PlotSettings(
        model=meta["model"],
        penlift=getattr(args, "penlift", 1),
        pen_down=getattr(args, "pen_down", 30),
        pen_type=getattr(args, "pen_type", "fineliner"),
    )


def cmd_estimate(args) -> int:
    svg, meta = _read_plot(args.plot)
    settings = _settings(args, meta)
    total = 0.0
    for layer in meta["layers"]:
        result = estimate(svg, layer["layer"], settings)
        total += result.seconds
        print(f"Layer {layer['layer']} ({layer['name']}): {format_duration(result.seconds)}, "
              f"{result.pendown_m:.2f} m of drawing")
    print(f"Total: {format_duration(total)} (plus pen changes)")
    return 0


def cmd_info(args) -> int:
    plotter = Plotter()
    if not plotter.connect(PlotSettings(model=1)):
        print("No plotter found. Plug in the USB cable and the power adapter.")
        return 1
    try:
        print(f"Firmware: {plotter.firmware()}")
        power = "OK" if plotter.power_ok() else "NOT DETECTED. Plug in the power adapter."
        print(f"Power adapter: {power}")
        identity = plotter.read_identity()
        if identity:
            print(f"Model: {get_model(identity.model).name} (label: {identity.label or 'none'})")
        else:
            print("Model: unknown. Run: rosetta-plot identify --model N")
    finally:
        plotter.disconnect()
    return 0


def cmd_identify(args) -> int:
    plotter = Plotter()
    if not plotter.connect(PlotSettings(model=args.model)):
        print("No plotter found. Plug in the USB cable and the power adapter.")
        return 1
    if plotter.write_identity(Identity(args.model, args.penlift, args.label)):
        print(f"Saved: this plotter is an {get_model(args.model).name}. It restarts now.")
        return 0
    plotter.disconnect()
    print("This plotter's firmware is too old to store its model (needs 2.5.5 or newer).")
    return 1


def cmd_trace(args) -> int:
    _svg, meta = _read_plot(args.plot)
    input(f"{HOME_INSTRUCTION} Then press Enter. ")
    plotter = Plotter()
    if not plotter.connect(_settings(args, meta)):
        print("No plotter found. Plug in the USB cable and the power adapter.")
        return 1
    try:
        plotter.trace(tuple(meta["ink_bbox"]))
    finally:
        plotter.disconnect()
    print("Traced the outline and returned Home.")
    return 0


def _run_with_pause(runner: PlotRunner, svg: str, layer: int, settings: PlotSettings, resume=False):
    """Run in a worker thread; Ctrl+C pauses instead of killing the plot."""
    holder = {}
    worker = threading.Thread(
        target=lambda: holder.setdefault("result", runner.run(
            svg, layer, settings, on_progress=_print_progress, resume=resume)),
        daemon=True,
    )
    worker.start()
    while worker.is_alive():
        try:
            worker.join(0.2)
        except KeyboardInterrupt:
            print("\nPausing...")
            runner.pause()
    print()
    return holder["result"]


def _print_progress(progress) -> None:
    print(f"\r  {progress.pendown_mm / 1000:.2f} m drawn", end="", flush=True)


def cmd_plot(args) -> int:
    svg, meta = _read_plot(args.plot)
    settings = _settings(args, meta)
    input(f"{HOME_INSTRUCTION} Then press Enter. ")
    runner = PlotRunner()
    layers = meta["layers"]
    for index, layer in enumerate(layers, start=1):
        input(f"Load the {layer['name']} pen ({index} of {len(layers)}), then press Enter. "
              f"(Ctrl+C pauses.) ")
        result = _run_with_pause(runner, svg, layer["layer"], settings)
        while result.outcome is not PlotOutcome.COMPLETED:
            if result.outcome is PlotOutcome.PAUSED:
                choice = input("Paused. [r]esume, [h]ome then resume, [q]uit: ").strip().lower()
                if choice == "q":
                    return 1
                resume_svg = result.resume_svg
                if choice == "h":
                    resume_svg = runner.return_home(resume_svg, settings)
                    input("The pen is Home. Press Enter to resume. ")
                result = _run_with_pause(runner, resume_svg, layer["layer"], settings, resume=True)
            elif result.outcome is PlotOutcome.DISCONNECTED:
                input("Plotter disconnected. Plug it back in, slide the pen Home, then press Enter. ")
                resume_svg = set_resume_origin_home(result.resume_svg)
                result = _run_with_pause(runner, resume_svg, layer["layer"], settings, resume=True)
            else:
                print(result.message)
                return 1
    print("Done! The pen is back Home.")
    return 0


def _add_pen_arguments(parser) -> None:
    parser.add_argument("--pen-down", type=int, default=30, help="pen-down height, percent (0-100)")
    parser.add_argument("--pen-type", choices=sorted(PEN_TYPES), default="fineliner")
    parser.add_argument("--penlift", type=int, choices=[1, 2, 3], default=1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="rosetta-plot", description="Rosetta Plotter (testing CLI)")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="turn a job file into a plot-ready SVG")
    prepare.add_argument("job", type=Path)
    prepare.add_argument("-o", "--out", type=Path, required=True)

    estimate_cmd = commands.add_parser("estimate", help="estimate plot time")
    estimate_cmd.add_argument("plot", type=Path)
    _add_pen_arguments(estimate_cmd)

    commands.add_parser("info", help="show the connected plotter")

    identify = commands.add_parser("identify", help="store the model on the plotter")
    identify.add_argument("--model", type=int, required=True, choices=sorted(MODELS))
    identify.add_argument("--penlift", type=int, choices=[1, 2, 3], default=1)
    identify.add_argument("--label", default="")

    trace = commands.add_parser("trace", help="trace the drawing's outline with the pen up")
    trace.add_argument("plot", type=Path)
    _add_pen_arguments(trace)

    plot = commands.add_parser("plot", help="plot, with pen-change prompts")
    plot.add_argument("plot", type=Path)
    _add_pen_arguments(plot)

    args = parser.parse_args(argv)
    handlers = {
        "prepare": cmd_prepare, "estimate": cmd_estimate, "info": cmd_info,
        "identify": cmd_identify, "trace": cmd_trace, "plot": cmd_plot,
    }
    try:
        return handlers[args.command](args)
    except ImportProblem as problem:
        print(str(problem))
        return 2
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests\test_cli.py -v`
Expected: `4 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv\Scripts\python -m pytest -v`
Expected: `115 passed`

- [ ] **Step 6: Commit**

```powershell
git add src\rosetta\cli.py tests\test_cli.py
git commit -m "feat: rosetta-plot CLI for hardware testing" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 20: Real exports from Illustrator 2026 and Affinity 3.3 (needs Adam)

This checks the size rules in `svgdoc.py` against real files instead of hand-written samples (spec §11.2).

**Files:**
- Create: `tests/files/real/*` (exported by Adam), `tests/files/real/manifest.json`, `tests/test_real_exports.py`
- Possibly modify: `src/rosetta/svgdoc.py` (`AFFINITY_PX_PER_INCH`)

- [ ] **Step 1: Adam makes the Illustrator files**

In Illustrator 2026:
1. **New document:** File › New, 200 mm × 100 mm, Units: Millimeters, **Color Mode: RGB**.
2. **Red square:**
   - Draw a rectangle.
   - In the Transform panel, set the reference point to top-left, then X 0, Y 0, W 100, H 100.
   - Stroke #FF0000 at 1 pt, fill None.
3. **Blue circle:**
   - Draw an ellipse.
   - Transform with the top-left reference: X 125, Y 25, W 50, H 50.
   - Fill #0000FF, stroke None.
4. **Text:** type `Hi` anywhere in black. Leave it as live text.
5. **Export the files** into `tests\files\real\`:

   | File | How to export |
   |---|---|
   | `ai_default.svg` | File › Export › Export As › SVG with the default options |
   | `ai_presentation.svg` | Export again, Styling: **Presentation Attributes** |
   | `ai_saved.pdf` | File › Save a Copy › Adobe PDF, default preset |
   | `ai_pdfcompat.ai` | File › Save As › .ai with "Create PDF Compatible File" checked (the default) |

6. **Second document:** File › New › Print › Letter, **Units: Points**, Color Mode RGB.
   - Draw a rectangle with the top-left reference at X 72, Y 72, W 72, H 72.
   - Stroke #FF0000, fill None.
   - Export As SVG with defaults to `ai_points.svg`.

- [ ] **Step 2: Adam makes the Affinity files**

In Affinity by Canva 3.3:
1. **New document:** 200 mm × 100 mm, RGB.
2. **Red square:**
   - Draw a rectangle.
   - In the Transform panel, set the anchor to top-left, then X 0, Y 0, W 100, H 100.
   - Stroke #FF0000 at 1 pt, no fill.
3. **Blue circle:** an ellipse at X 125, Y 25, W 50, H 50, fill #0000FF, no stroke.
4. **Export** into `tests\files\real\`:

   | File | How to export |
   |---|---|
   | `affinity_default.svg` | File › Export › SVG, default preset |
   | `affinity.pdf` | File › Export › PDF, default preset |

- [ ] **Step 3: Write the manifest**

`tests/files/real/manifest.json`:
```json
{
  "ai_default.svg":       {"size": [200, 100], "red": [0, 0, 100, 100], "blue": [125, 25, 175, 75], "issues": ["text"]},
  "ai_presentation.svg":  {"size": [200, 100], "red": [0, 0, 100, 100], "blue": [125, 25, 175, 75], "issues": ["text"]},
  "ai_saved.pdf":         {"size": [200, 100], "red": [0, 0, 100, 100], "blue": [125, 25, 175, 75], "issues": ["pdf_text"]},
  "ai_pdfcompat.ai":      {"size": [200, 100], "red": [0, 0, 100, 100], "blue": [125, 25, 175, 75], "issues": ["pdf_text"]},
  "ai_points.svg":        {"size": [215.9, 279.4], "red": [25.4, 25.4, 50.8, 50.8], "blue": null, "issues": []},
  "affinity_default.svg": {"size": [200, 100], "red": [0, 0, 100, 100], "blue": [125, 25, 175, 75], "issues": []},
  "affinity.pdf":         {"size": [200, 100], "red": [0, 0, 100, 100], "blue": [125, 25, 175, 75], "issues": []}
}
```

- [ ] **Step 4: Write the test**

`tests/test_real_exports.py`:
```python
import json
from pathlib import Path

import pytest

from rosetta.geometry_testing import shapes_bbox
from rosetta.loader import load_artwork

REAL = Path(__file__).parent / "files" / "real"
MANIFEST = json.loads((REAL / "manifest.json").read_text(encoding="utf-8"))
SIZE_TOLERANCE_MM = 0.2


@pytest.mark.parametrize("name", sorted(MANIFEST))
def test_real_export(name):
    expected = MANIFEST[name]
    art = load_artwork(REAL / name)
    assert (art.width_mm, art.height_mm) == pytest.approx(expected["size"], abs=SIZE_TOLERANCE_MM)
    red = [shape for shape in art.shapes if shape.color == "#ff0000"]
    assert shapes_bbox(red) == pytest.approx(expected["red"], abs=SIZE_TOLERANCE_MM)
    if expected["blue"] is not None:
        blue = [shape for shape in art.shapes if shape.color == "#0000ff"]
        assert shapes_bbox(blue) == pytest.approx(expected["blue"], abs=SIZE_TOLERANCE_MM)
    codes = {issue.code for issue in art.issues} - {"fill_only"}
    assert codes == set(expected["issues"])
```

- [ ] **Step 5: Run it**

Run: `.venv\Scripts\python -m pytest tests\test_real_exports.py -v`
Expected: `7 passed`. If something fails, fix it this way:

- **`affinity_default.svg` is the wrong size.**
  - Divide the expected 200 by the measured width.
  - Set `AFFINITY_PX_PER_INCH` in `src/rosetta/svgdoc.py` to 96 divided by that ratio. For example, measured 266.67 → ratio 0.75 → set it to 72.0.
  - Update `AFFINITY_EXPORT` in `tests/samples.py` so its viewBox matches the new value. For 72: `viewBox="0 0 283.4646 141.7323"` with the path `M28.3465,28.3465L283.4646,28.3465`.
  - Rerun the full suite.
- **An Illustrator SVG is detected as `svg` instead of `illustrator`** (the size comes out at 133%). Add the fingerprint that file actually contains to `detect_source`, add a matching sample, and rerun.
- **The issue codes differ** (for example, Affinity exported text as curves). Change the manifest only if the file is right and the expectation was wrong. Note why in the commit message.

Record any rule change as a one-line note in spec §6.2 under "Percent sizes".

- [ ] **Step 6: Commit**

```powershell
git add tests\files\real tests\test_real_exports.py src\rosetta\svgdoc.py tests\samples.py docs
git commit -m "test: verify sizing against real Illustrator 2026 and Affinity 3.3 exports" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 21: First real plots on the lab's large AxiDraw (needs Adam and the plotter)

This is the spec §11.4 checklist, run through the CLI. Record the results in `docs/hardware-log.md`.

**Files:**
- Create: `docs/hardware-log.md`, `out/` job files (git-ignored)

- [ ] **Step 1: Identify the plotter**

Plug in USB and power, then run:
```powershell
.venv\Scripts\rosetta-plot info
```
Expected: firmware, `Power adapter: OK`, and `Model: unknown`.
- Find the model with spec §12: read the label, or measure the travel. SE/A1 is model 5, SE/A2 model 6, V3 XLX model 3.
- Then run `.venv\Scripts\rosetta-plot identify --model N --label "PSU Lab"`.
- Run `info` again. Expected: the model name.

- [ ] **Step 2: Prepare a measurable test job**

Save `out\square.svg`, a 100 mm red square at (20 mm, 20 mm) on a Letter page:
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="215.9mm" height="279.4mm" viewBox="0 0 215.9 279.4">
  <rect x="20" y="20" width="100" height="100" fill="none" stroke="#ff0000"/>
  <line x1="20" y1="140" x2="120" y2="140" stroke="#000000"/>
</svg>
```
Save `out\job.json`, replacing `N` with the model number:
```json
{"model": N, "material": {"x": 0, "y": 0, "width": 215.9, "height": 279.4}, "pieces": [{"path": "square.svg", "x": 0, "y": 0}]}
```
Run:
```powershell
.venv\Scripts\rosetta-plot prepare out\job.json -o out\plot
.venv\Scripts\rosetta-plot estimate out\plot.svg
```
Expected: `2 pen colors` (red, then black), plus a time per layer.

- [ ] **Step 3: Trace and plot**

1. Tape Letter paper with its corner exactly at the Home corner.
2. Run `.venv\Scripts\rosetta-plot trace out\plot.svg --pen-down 30`. Check that the pen outlines the region from (20, 20) to (120, 140) mm.
3. Run `.venv\Scripts\rosetta-plot plot out\plot.svg --pen-down 30` and follow the prompts.
   - During the red layer, press **Ctrl+C**, choose `r`, and confirm it resumes cleanly.
   - Press the plotter's physical pause button once and confirm the same.

- [ ] **Step 4: Measure and log**

With a ruler:
- the square's left and top edges should be 20 mm from the paper edges (±1 mm);
- each side should be 100 mm (±1 mm);
- the black line should sit 140 mm from the top edge.

Then test unplugging:
- Repeat the plot, unplug USB mid-red, and follow the prompts (replug, slide Home, Enter).
- Confirm the plot continues where it stopped.

Write each result (pass/fail plus the measurements) into `docs/hardware-log.md` with the date and model.

- [ ] **Step 5: Commit**

```powershell
git add docs\hardware-log.md
git commit -m "docs: first hardware log on the lab AxiDraw" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
