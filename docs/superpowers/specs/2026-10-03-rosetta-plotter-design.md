# Rosetta Plotter — Design Spec

**Date:** 2026-10-03
**Author:** Adam Leonardini (research assistant), with Claude
**For:** Portland State University, plotting with Evil Mad Scientist AxiDraw pen plotters
**Status:** Design approved in conversation, pending written-spec review
**Name:** **Rosetta Plotter** (chosen by Adam). It deliberately avoids "AxiDraw," which is EMS's trademark.

---

## 1. Purpose

Students currently plot through Inkscape's AxiDraw extension. Its interface is hard to use, and Inkscape is a poor fit for students who design in Illustrator or Affinity. The app replaces that workflow with a standalone Windows program. It walks a student through a plot one step at a time, and its interface is about as complex as Windows Photos or Paint.

**Users:** students with limited technical ability, on their own Windows laptops, who plug into a shared plotter when it's their turn.

**Success criteria:**
- A first-time student can go from "plotter on the table" to a correct plot without outside help.
- The drawing lands on the paper where the screen shows it, within ±1 mm.
- Students never see motor settings, SVG internals, or Inkscape concepts unless they open "Advanced."

## 2. Constraints

- **Platform:** Windows 10 and 11 only.
- **Hardware:** every AxiDraw model the EMS software supports:
  - V2/V3/SE-A4, V3/A3 and SE/A3, V3 XLX, MiniKit, SE/A1, SE/A2, V3/B6
  - both standard and brushless pen-lift servos
- **Out of scope:** Bantam Tools NextDraw.
- **Schedule:** as soon as possible. Version 1 is the core flow and ships first; further features follow as updates (§9).
- **License and distribution:** the app bundles EMS's GPL-licensed engine, so it must be released as open source. PyMuPDF (PDF import) is AGPL, so the app is licensed **AGPL-3.0**. It's published on Adam's personal GitHub account, and installers are attached to GitHub Releases.
- **Unsigned installer:**
  - Students will see Windows SmartScreen's "Windows protected your PC" on first run.
  - The one-page **Quick Start** (PDF + README section) opens with a screenshot: click **More info**, then **Run anyway**.
  - Build in PyInstaller's one-folder mode, which antivirus tools flag less often than one-file builds.
  - If Microsoft Defender flags a release, submit it for false-positive review at the Microsoft Security Intelligence portal.

## 3. Architecture

```
┌──────────────────────── Windows app (one installer) ────────────────────────┐
│                                                                             │
│  UI (HTML/CSS/TypeScript in a WebView2 window via pywebview)                │
│    step bar · canvas · dialogs · Fluent UI web components                   │
│        │  calls / events (pywebview js_api bridge, JSON)                    │
│        ▼                                                                    │
│  App core (Python 3.12)                                                     │
│    ├─ session    : current machine, material, pieces, pen settings         │
│    ├─ translate  : import → normalize → flatten → place → clip → group     │
│    ├─ engine     : wrapper around EMS pyaxidraw 3.9.6 (unmodified)          │
│    │                 connection · jog/trace/pen test · plot runner · status │
│    └─ settings   : per-laptop JSON + per-plotter profile                   │
│        │                                                                    │
│        ▼  USB serial (EiBotBoard, VID:PID 04D8:FD92)                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Technology decisions:**

| Concern | Choice | Why |
|---|---|---|
| Plot engine | EMS AxiDraw Python API v3.9.6, pinned and unmodified | Proven motion planning, preview, pause/resume, and hidden-line removal; plots behave the same as the official software |
| Runtime | Python 3.12, bundled | The EMS API supports Python 3.8–3.12 |
| Window and UI | pywebview with the Edge WebView2 backend; front end in TypeScript built with Vite | WebView2 ships with Windows 11. It renders imported SVG exactly, which Qt's SVG Tiny renderer does not. Fluent components give a Windows 11 look |
| UI components | Microsoft Fluent UI Web Components | Native Windows look and feel |
| PDF / .ai import | PyMuPDF: convert the page to SVG, with text converted to paths | Every input then runs through one SVG pipeline |
| Geometry | The EMS digest parser (`axidrawinternal.digest_svg`) for parsing and flattening, plus our own clipping | Whatever the screen shows is what the engine will draw |
| Packaging | PyInstaller (one folder) plus an Inno Setup installer; the installer bootstraps WebView2 if it's missing | Standard and reliable on Windows |
| Dev environment | A `.venv` built with `py -3.12` (Python 3.12 is already installed at `C:\Users\leona\Python312`) | The machine's default Python is 3.14, which the EMS API doesn't support |

## 4. Coordinate systems (must be exact)

**Machine frame.** All internal geometry uses this frame, in millimetres.
- **Origin (0,0) is the Home corner.** That's the carriage's travel limit farthest left and farthest back, next to the engraved "HOME" label and the USB port.
- **+x** runs to the student's right when they stand in front of the plotter.
- **+y** runs toward the student, the direction the pen arm extends.
- **Reachable area** is `[0, travel_x] × [0, travel_y]`, using the EMS model table:

| Model | travel_x × travel_y (mm) |
|---|---|
| V2/V3/SE-A4 | 300 × 218 |
| V3/A3, SE/A3 | 430 × 297 |
| V3 XLX | 595 × 218 |
| MiniKit | 160 × 101.6 |
| SE/A2 | 594 × 432 |
| SE/A1 | 864 × 594 |
| V3/B6 | 190 × 140 |

**Screen.**
- The canvas draws the machine frame directly. The machine body is at the top of the screen and the pen arm reaches toward the bottom, so the Home corner is always the top-left of the canvas.
- The app never auto-rotates. The engine's `auto_rotate` is always `False`.

**Material.** A rectangle in the machine frame: `origin (mx, my)`, `width`, `height`.
- `(mx, my)` is the paper's corner nearest Home.
- It defaults to `(0, 0)`, "lined up with the Home corner."
- "Mark this corner" sets `(mx, my)` to the pen's current position.

**Artwork piece.** Each piece has a transform relative to the material origin: translate `(tx, ty)`, a uniform scale `s`, and a rotation `r` that's a multiple of 90°.

**Wording rule.** UI text never uses "top," "bottom," "upper," or "lower" for corners. It always refers to the HOME label, the USB port, or the illustration.

**Units.** The UI shows inches by default, with a toggle to mm. Everything internal is mm. The plot-ready SVG uses mm, with a matching `viewBox`.

## 5. The student's flow

A step bar across the top reads **1 Plotter → 2 Material → 3 Artwork → 4 Pen → 5 Plot**. The first time through, the steps unlock in order. After that the student can move between them freely. Each screen has one primary action, a single instruction sentence, and an illustration. "Advanced" links lead to the engine options (speeds, acceleration, pen timing, optimization, resolution).

### Step 1 — Plotter
1. **Connect.** The app scans for the EiBotBoard automatically. If none is found: "Plug in the USB cable and the power adapter," with a picture of both ports.
2. **Power check.** Read the input voltage (the engine's voltage check). If it's low: "The power adapter isn't plugged in. The pen can't move without it."
3. **Identify the model.** Read the board's nickname.
   - If it's in our format (§8), the model is known.
   - Otherwise ask "Which AxiDraw is this?" with photos and sizes, then write the nickname so other laptops recognize this plotter.
4. **Home.**
   - Turn the motors off.
   - Instruction: "Gently slide the pen to the corner next to the HOME label and the USB port." The illustration highlights that corner.
   - Button: **"It's in the corner."**
   - The app now treats the pen as being at (0,0).

### Step 2 — Material
1. **Size.**
   - Preset cards: Letter, Legal, Tabloid 11×17, A4, A3, A2, A1, plus Custom (width × height).
   - A portrait/landscape toggle.
   - Presets bigger than the reachable area stay selectable, but the unreachable part of the paper is shown greyed out.
2. **Position.**
   - **"Lined up with the Home corner"** (the default) sets the origin to (0,0).
   - **"Somewhere else"**:
     - Arrow buttons move the pen with the pen up, at fine (1 mm) or coarse (10 mm) steps.
     - Instruction: "Move the pen over your paper's corner nearest the HOME label, then click **Mark this corner**."
     - Alternatively, drag the paper rectangle on the canvas or type X/Y values.
   - Before leaving this step, the pen returns to (0,0).
3. **Canvas.** Shows the reachable area, the paper rectangle, and the greyed-out unreachable region.

### Step 3 — Artwork
1. **Import.**
   - An **Import** button, plus drag and drop.
   - Accepted: `.svg`, `.pdf`, and `.ai`. An `.ai` file opens only if it was saved with PDF compatibility, which is Illustrator's default.
   - A multi-page PDF asks which page to use.
   - `.afdesign` files are refused with: "In Affinity, use File › Export › SVG or PDF."
2. **Placement on import.** The piece is centered on the paper. If it's larger than the paper inside the margins, it's scaled down to fit and the app says so.
3. **Arrange.**
   - Drag to move. Corner handles scale it, always keeping proportions.
   - Rotate 90° buttons, Center-on-paper, and Delete/Duplicate.
   - Exact position and size fields.
   - Margin guides (default 0.25 in, adjustable). They're visual only, plus the boundary used for auto-fit on import. Clipping happens at the paper edge, not the margin.
4. **Pieces panel.** Lists the imported pieces, each with a problem badge if it has any (§6.3).
5. **Off-paper.** Geometry outside the paper shows in red and is clipped away at plot time. Plotting is blocked only if nothing drawable remains.

### Step 4 — Pen
1. "Put your pen in the holder," with an illustration. Buttons: **Raise pen** and **Lower pen**.
2. **Pen-height slider** (pen-down height, 0–100%). Dragging it moves the real pen live through the engine's interactive context.
   - Pen-up height is `max(60, down + 20)`, capped at 100. It can be changed under Advanced.
3. **Optional test mark:** a 10 mm line drawn just inside the paper's corner nearest Home.
4. **Pen type cards.** Each sets the pen-down speed (percent of maximum). Pen-up speed is 75% for all. These starting values get tuned during hardware testing:
   - Fine liner: 25 (the EMS default)
   - Marker: 35
   - Brush / paint pen: 12

### Step 5 — Plot
1. **Summary:** estimated time (from an engine preview-mode dry run), number of pens and colors, and any warnings that remain.
2. **Preview.** Animates the planned path: pen-down moves in color, pen-up moves faint. It can be scrubbed.
3. **Trace outline.** With the pen up, the plotter moves around the bounding box of all the clipped artwork, then returns Home. There's a "Trace again" button.
4. **Start.**
   - The canvas shows a live pen dot, and lines darken as they're drawn.
   - A progress bar shows time remaining.
   - Buttons: **Pause** and **Stop**. The physical button on the plotter also pauses.
5. **Pen changes.** Between color groups the pen returns Home and a dialog says: "Swap to the **red** pen (2 of 3), then click Continue." The dialog shows a color swatch.
6. **Finish.** The pen goes Home and the app shows "Done!" with **Plot another copy** ("Put a fresh sheet in the same spot") and **New plot**.

## 6. Components

### 6.1 `engine` — EMS API wrapper
**Owns** the single connection to the plotter. It exposes:
- `connect()` / `disconnect()`, `find_plotters()`
- `power_ok()`
- `read_identity()` / `write_identity(model, penlift, label)`
- `motors_off()`, `set_home()` (record the current position as (0,0))
- `jog(dx, dy)`, `goto(x, y)` with the pen up
- `pen_up()`, `pen_down()`, `set_pen_height(pct)`
- `trace(rect)`
- `plot(plot_svg, layer, options, on_progress, pause_event)` returns a `PlotResult` (completed / paused / stopped / disconnected, plus the resume SVG)
- `resume(resume_svg, ...)`
- `estimate(plot_svg, layer, options)` returns time and distance (preview mode, no hardware)

**Rules:**
- **Contexts.** Jogging, tracing, and pen tests use the EMS *interactive* context. Plots use the *plot* context.
  - Before switching from interactive to plot, the wrapper always returns the pen to (0,0) and disconnects, because the plot context assumes it starts at Home.
- **Threads.** The plot runs in a worker thread. Live position comes from polling `ad.pen.phys.xpos/ypos` every 100 ms. That's an internal attribute, which is acceptable because the engine version is pinned.
- **Pause.** Uses `set_up_pause_receiver(threading.Event)`.
- **Resume.** Uses the engine's `res_plot` mode with the SVG returned by `plot_run(True)`.
- **Sleep.** `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` keeps the laptop awake for the length of a plot.
- **Fixed engine options:**
  - `auto_rotate=False`
  - `model` and `penlift` taken from the plotter identity
  - `reordering=2` (reorder and allow reversal) unless Advanced changes it
  - `hiding=False` unless Advanced turns it on

### 6.2 `translate` — files to a plot-ready SVG
**Pipeline**, run per piece on import and cached:
1. **Load.** SVG as-is. PDF and AI pages through PyMuPDF, converted to SVG with text as paths.
2. **Normalize the SVG.**
   - **Size.** Unitless or `px` root width and height are read at 96 px/in. If the file shows Illustrator's markers (an `Adobe Illustrator` generator comment or `data-name` attributes) and its width and height are unitless or `px`, it's read as pt (72/in). That's the same fix EMS applies in `process_ai`.
   - **Percent sizes.** A `%` width or height (common in Affinity exports) falls back to the `viewBox` read in px at 96/in. *This rule must be checked against real Affinity 3.3 exports during testing (§11), and changed if they show otherwise.*
   - **Inline CSS.** Rules in `<style>` elements are written into each element's `style` attribute. `tinycss2` parses the rules, and a small built-in matcher handles simple selectors: tag, `.class`, `#id`, and combinations like `path.cls-1`. That's all Illustrator and Affinity emit. Illustrator's default "Internal CSS" export puts every color in `<style>` classes, and the EMS parser doesn't read those. Without this step, every Illustrator path would look unpainted.
3. **Flatten.** Run the EMS `digest_svg.DigestSVG` parser (curve tolerance 0.002 in), which produces polylines, each tagged with its stroke and fill colors.
4. **Clean up.** Paths whose fill is explicitly `none` *and* whose stroke is `none` or unset are dropped. These are invisible helper shapes that the engine would otherwise draw.
   - SVG's default fill is black, so a path with no fill attribute counts as a black-filled shape.
5. **Place.** Apply the piece transform (§4).
6. **Clip.** Clip the polylines to the intersection of the paper and the reachable area.
7. **Group by pen.** Group the polylines by color: the stroke color, or the fill color for fill-only shapes. Groups are ordered by first appearance in the file.
8. **Emit.** Write one plot-ready SVG:
   - Root `width`/`height` equal the reachable area in mm.
   - One Inkscape layer per color group, named `1`, `2`, `3`, …
   - Every element is a `<polyline>` in machine coordinates. No transforms, no styles beyond stroke color.
   - Each color group plots as its own engine run in `layers` mode. The app shows the pen-change dialog between runs, and the engine returns Home after each run.

### 6.3 Problem checker (runs during translate)

| Detected | Message (plain language) | v1 action |
|---|---|---|
| `<text>` in SVG | "This file has live text, which can't be drawn. In Illustrator or Affinity, convert text to outlines and export again." | Text is skipped |
| `<image>` | "Pictures can't be drawn, only lines. The picture will be skipped." | Skipped |
| Fill-only shapes | "These shapes are solid fills. The plotter draws only their outlines." | Outline drawn (engine default) |
| White strokes or fills (often a background rectangle) | "There's a white shape here, probably a background. Skip it?" | Skip by default, with a toggle |
| `clip-path` / masks | "This file uses a clipping mask. The hidden parts will be drawn too. Release or expand the mask before exporting." | Warn only |
| Text in PDF/AI (converted to outlines) | "Text will be drawn as outlined letters (double lines)." | Informational |
| Nothing drawable | "This file has no lines to draw." | The import is refused |

### 6.4 `session` and `settings`
- **Session:** the machine identity, material, list of pieces (file reference, cached geometry, transform), pen settings, and plot state.
- **Settings:** stored as `%APPDATA%\RosettaPlotter\settings.json`. Contents:
  - units
  - last material
  - pen-type speed presets
  - per-plotter profiles keyed by nickname: pen-down height, pen type
  - advanced options

### 6.5 UI
- **Window.** A single WebView2 window. The minimum size is 1024 × 700, and the layout fits laptop screens.
- **Canvas.** An SVG scene drawn in the machine frame. Artwork renders natively, with the browser's SVG rendering of the original file shown under the cached geometry. Selection handles and margin guides draw on top.
- **Bridge.** UI ↔ Python goes through the pywebview `js_api`. Long operations (import, estimate, plot) return immediately and push progress events to the UI.

## 7. Data flow (one plot)

```
files ─► translate (per piece, cached) ─► session.pieces
                                              │
material + pieces + pen ─► translate.emit ─► plot-ready SVG (layers 1..N)
                                              │
              engine.estimate (preview) ◄─────┤
              engine.trace(bbox) ◄────────────┤
                                              ▼
for each layer k: engine.plot(svg, layer=k) ─► progress events ─► canvas dot / bar
                   └─ paused? ─► resume SVG kept in session ─► engine.resume
              between layers: pen-change dialog
```

## 8. Plotter identity (works across laptops)

- **Where it's stored.** The model and pen-lift type are written to the EiBotBoard's nickname, which needs firmware 2.5.5 or newer and holds up to 16 characters. The format is `<label> m<model>p<penlift>`, truncated so the suffix always fits. Example: `PSU Lab A m2p1`.
- **Rebooting.** Writing the nickname reboots the board. The app reconnects automatically.
- **Older firmware.** Below 2.5.5 the identity is stored only on the laptop, keyed by serial port. The app says once: "This plotter's firmware is old. You'll be asked for the model on each laptop."

## 9. Scope

**Version 1:** everything in §5 and §6. That covers:
- installer, connect, power check, model identity
- Home step, material presets and custom sizes, both placement modes
- SVG, PDF, and AI import, with the problem checker
- arranging multiple pieces with off-paper clipping
- pen step with live height
- preview, time estimate, trace outline
- plotting with the live dot, pause/resume/stop, and pen-change prompts
- "Plot another copy"
- settings remembered on each laptop

**Later updates** (each gets its own spec):
- Hatch fill for filled shapes
- A text tool with single-line Hershey fonts
- Save and open project files
- Hidden-line removal surfaced as a simple toggle (v1 has it under Advanced only)
- Resuming after an app crash or restart (v1 resumes within the same session only)
- A shareable lab profile file for the professor
- Two-corner alignment for crooked paper
- Applying clipping masks automatically
- Letting students reorder pen colors
- "Send to plotter" buttons inside Illustrator (CEP panel or UXP) and Affinity (script)
- An update-available notice

**Not planned:** drawing or editing tools, NextDraw, macOS.

## 10. Error handling

Every message is one sentence about what happened and one about what to do, with a "Details" link. **Copy diagnostics** puts the recent log and system info on the clipboard. Logs rotate under `%APPDATA%\RosettaPlotter\logs\`.

| Situation | Behavior |
|---|---|
| No plotter found | Connect screen with a cable-and-power picture. Retries automatically every 2 s. |
| Low voltage or no power adapter | Blocks plotting with the power message. Checked at connect and before every plot. |
| USB lost mid-plot | The engine reports disconnected. The app saves the resume SVG and says: "Plotter disconnected. Plug it back in, slide the pen Home, then click Resume." After the student re-homes, the app sets the last position in the resume data to (0,0), so the resumed plot travels out from Home. |
| Paused (button, app, or physical) | The pen lifts. Options: Resume, Return Home, Cancel plot. |
| App closed mid-plot | Confirmation dialog. If confirmed: pause, pen up, then close. |
| System sleep | Blocked during plots. Banner: "Keep the laptop open while plotting." |
| Carriage bumped or pen snag | Can't be detected (the plotter has no sensors). A **Re-home** button stays visible on every step. Trace outline is recommended before the first plot. |
| Import failure | A specific reason (unreadable, no drawable lines, unsupported format with the export instruction). |
| Engine exception | Caught at the wrapper. The pen is raised if the plotter is still connected, and the user sees a generic message plus Details. |

## 11. Testing

1. **Unit tests (pytest), no hardware:**
   - Units and size normalization: Illustrator in pt, mm, and in; Affinity; Inkscape.
   - Inlining CSS (Illustrator "Internal CSS" and "Presentation attributes" exports must produce identical geometry and colors), flattening, the transform math (translate, scale, 90° rotation), clipping, and color grouping.
   - Coordinate frames: the material offset plus the piece transform gives the expected machine coordinates.
2. **Golden-file tests:**
   - A library of real exports, saved in `tests/files/`, from Illustrator 2026 (30.8.1) and Affinity by Canva 3.3.0: pt and mm documents, layers, text, fills, white backgrounds, clipping masks, and multiple artboards or pages.
   - Each one's plot-ready SVG output is compared against a reviewed expected file.
3. **Engine dry runs, no hardware.** Every golden file goes through `engine.estimate` (preview mode) to assert that bounds stay inside the paper and the times are sensible.
4. **Hardware checklist, on a real plotter.** Each item gets measured with a ruler where relevant:
   - Home accuracy, and lined-up placement within ±1 mm.
   - Mark-corner placement within ±1 mm.
   - Trace outline matches the on-screen bounding box.
   - Pen-height slider responds live.
   - Multi-color pen changes.
   - Pause/resume from the app and from the physical button.
   - USB unplugged mid-plot, then resume.
   - Power adapter missing.
   - The lab's large plotter is the hardware test machine. It's an SE/A1, SE/A2, or V3 XLX; the exact model is confirmed with the identification steps in §12.
   - Other models aren't tested on hardware. They differ only in their travel limits (§4), so they're checked with engine dry runs using each model's setting.
5. **Usability session.** Two or three students who have never used the app try it with no help. Note where they hesitate, then fix the wording and flow before wider release.

## 12. Decisions and remaining items

**Decided 2026-10-03:**
- Name: **Rosetta Plotter**.
- Published on Adam's GitHub under AGPL-3.0.
- The installer is unsigned, with the SmartScreen instructions in the Quick Start (§2).

**Remaining:** confirm the test plotter's exact model before the hardware checklist (§11.4).
- **Fastest:** read the model label on the machine.
- **Otherwise, measure.** Turn the motors off, slide the pen from Home all the way to the right, and measure how far it travelled. Then measure how far the pen arm reaches toward you.

| Pen travel to the right | Pen-arm reach toward you | Model |
|---|---|---|
| about 86 cm (34 in) | about 59 cm (23 in) | SE/A1 |
| about 59 cm (23 in) | about 43 cm (17 in) | SE/A2 |
| about 59 cm (23 in) | about 22 cm (8.6 in) | V3 XLX |
