# Rosetta Plotter — Manager UI Design Spec

**Date:** 2026-10-07
**Author:** Adam Leonardini (research assistant), with Claude
**Status:** Design approved in conversation, pending written-spec review
**Supersedes:** in `2026-10-03-rosetta-plotter-design.md`, §5 (the guided five-step flow) and the UI parts of §6.5 (step bar, Fluent UI). Everything else in that spec still stands: architecture, coordinates, engine rules, translate pipeline, problem checker, identity, error handling and testing.
**Builds on:** the Python app layer from Plan 2a and its contract in `docs/bridge.md`.

---

## 1. What changed and why

The student app is now a **manager**, not a wizard:
- It's modeled on **Rayjet Manager**, Trotec's laser job manager.
- It's arranged like **Adobe Illustrator**.
- Its plate is drawn like **Rhino's Top view**.

Adam's direction:
- "It doesn't have to guide the user but needs to be easily maneuverable."
- Architecture students already work in Illustrator and Rhino, so the familiar layout is the guidance.

**Success criteria:**
- A student who has seen the app once can import, place and plot without help.
- Every action can be reached from a menu and from a visible control, and the common ones have shortcuts.
- Placed drawings plot where the screen shows them, within ±1 mm.
- Students never see motor settings, SVG internals or Inkscape concepts unless they open the Advanced settings.

**Decisions:**

| Topic | Decision |
|---|---|
| Guidance | **Fully manual.** Nothing pops up except the pen-change dialog, the close-mid-plot confirmation and the Stop confirmation. A control that can't work yet is greyed out, and its tooltip says why (§6). |
| Jobs | A **Rayjet-style job queue.** Imported files wait in a Jobs list and are placed onto the paper by double-click or drag. A job can be placed several times. |
| Layout | **Illustrator's arrangement:** menu bar, a context control bar, a tools column on the left, and docked panels on the right. |
| Plate | **Rhino's Top view:** grid, red X and green Y axes from Home, the dashed reach, and the paper. |
| Theme | **Dark**, like Illustrator's default. |
| Toolkit | **Custom compact:** TypeScript + Lit + our own styling. Fluent UI is dropped because its controls are sized for touch and the look here is a dense desktop tool. |
| Placement | Drawings are placed at **100%, never auto-shrunk.** Architecture drawings are to scale. Off-paper parts show red and aren't drawn. Fit to paper is a menu command. A drawing's **origin is always its top-left corner** (the corner nearest Home), and X/Y always refer to it. |
| Rotation | **Free rotation:** the Rotate tool turns a drawing to any angle, Shift snaps to 15°, and the angle can be typed. **Rotate paper** turns the paper and everything on it 90°. |
| Units | **Decimal inches, millimetres, centimetres.** No measurements are drawn on the work area; dimensions appear in the control bar for whatever is selected. |
| Pens | A Pens panel lists the colors in plot order. An **eye toggle skips a color** in the plot. |

## 2. The window

```
┌ Menu bar: Rosetta Plotter  File  Edit  Object  View  Plotter  Help ─────────────────────────┐
├ Control bar (changes with context) ……………………………… pen times · total │ Start  Pause  Stop ┤
├────┬───────────────────────────────────────────────────────────────┬────────────────────────┤
│Tool│                                                               │ Jobs            [+Import]│
│ s  │                    Plate (canvas)                             │  site-plan.svg   ✓       │
│    │   grid · axes from Home · reach (dashed) · paper · drawings   │  logo.ai         ⚠       │
│    │   · selection handles · pen crosshair                         ├────────────────────────┤
│    │   (notification strip appears across the top when needed)     │ Pens                     │
│    │                                                               │  👁 ■ 1 Black     4:10   │
│    │                                                               │  👁 ■ 2 Red       0:52   │
│    │                                                               ├────────────────────────┤
│    │                                                               │ Plotter                  │
│    │                                                               │  Paper · Pen · Height    │
│    │                                                               │  jog pad (1 / 10 mm)     │
├────┴───────────────────────────────────────────────────────────────┴────────────────────────┤
│ Status bar: plotter + model · power · Home set · pen X,Y · cursor X,Y ……………………… in | mm   │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Window size:** minimum 1024 × 700 (spec §6.5). The right dock is 220 px wide by default, can be resized from 180 to 320 px, and each panel collapses to its header.

### 2.1 Menu bar
| Menu | Items (shortcut) |
|---|---|
| File | Import… (Ctrl+I) · Settings… (Ctrl+,) · Copy diagnostics · Exit |
| Edit | Undo (Ctrl+Z) · Redo (Ctrl+Shift+Z) · Delete (Del) · Select all (Ctrl+A) · Deselect (Ctrl+Shift+A) |
| Object | Duplicate (Ctrl+D) · Rotate 90° clockwise (Ctrl+R) · Rotate paper 90° (Ctrl+Shift+R) · Center on paper (Ctrl+Shift+C) · Fit to paper · Remove job from list |
| View | Fit paper in window (Ctrl+0) · Fit reach in window (Ctrl+Alt+0) · Zoom in (Ctrl+=) · Zoom out (Ctrl+-) · Units › Inches / Millimeters / Centimeters · Show grid · Show margins · Show rulers (off by default) · Show original artwork · Snap (on by default) |
| Plotter | Set Home · Plotter model… · Move pen Home · Trace outline · Preview path · Start (Ctrl+Enter) · Pause (Ctrl+Shift+P) · Stop |
| Help | Quick Start · Keyboard shortcuts · About Rosetta Plotter |

**Undo** covers placement edits only: move, scale, rotate, rotate paper, duplicate, delete and place. It never covers plotter actions.

### 2.2 Control bar (context)
- **A placed drawing is selected:** the drawing's name, then its **X, Y** (its top-left corner), **W, H** (proportions always locked, so W and H change together) and **angle** (any value; typed or set with the Rotate tool). With several selected, the values describe the box around them all.
- **Nothing selected:**
  - **Paper** size (the presets from spec §5.2 plus Custom) with its **W, H** readout, **orientation**, and the paper's **X/Y** (its corner nearest Home; 0, 0 = lined up with Home);
  - **Mark corner at pen**, which sets X/Y to the pen's position;
  - **margin**.
- **Right end, always shown:**
  - colored chips with each visible pen's time, then the **total**;
  - **Start** (the one accent-filled button), **Pause** and **Stop**.
  - While plotting, the total becomes **time remaining** and a thin progress line runs along the bar's bottom edge.
  - While paused, Start/Pause/Stop are replaced by **Resume · Return Home · Cancel plot**.

### 2.3 Tools column (left)
| Group | Tools (shortcut) |
|---|---|
| Navigate | Select (V) · Hand (H, or hold Space) · Zoom (Z; Alt-click zooms out) |
| Plotter | Move pen to point (P, a click on the plate moves the pen there, pen up) · Set Home · Trace outline · Preview path |
| Arrange | Rotate (R; drag around the selection to turn it about its center, Shift snaps to 15°; double-click the tool to type an angle) · Rotate paper 90° · Center on paper · Duplicate · Delete |

Every tool has a tooltip with its name and shortcut. The active tool is highlighted.

### 2.4 Plate (canvas)
- **Frame:** the machine frame (spec §4). Home is the top-left corner. Red X runs along the rail, green Y toward the student.
- **No numbers or labels on the work area.** Dimensions live in the control bar and the status bar. Rulers (in the current units) appear only if View › Show rulers is on.
- **What's drawn:**
  - the dark grid, at a 10 mm minor step (0.25 in in inches), with every 5th line stronger;
  - the dashed **reach** of the connected model;
  - the **paper** as a light sheet, with any part beyond the reach shaded;
  - margin guides, as a toggle;
  - the **placed drawings**: the lines the plotter will draw, colored by pen, with off-paper parts red and hidden pens faded;
  - optionally, the original artwork faintly underneath;
  - **selection** handles, as corner squares;
  - the **pen crosshair** when the position is known.
- **Interaction:**
  - Wheel zooms around the cursor. Hand or Space-drag pans. Fit paper and fit reach are commands.
  - **Select:** click a drawing to select it, Shift-click to add, drag on empty space to marquee.
  - **Move:** drag the selection. Drag a corner handle to scale proportionally around the opposite corner.
  - **Rotate:** with the Rotate tool, drag around the selection to turn it about its center (Shift snaps to 15°). A rotated drawing's X/Y/W/H describe its upright bounding box.
  - **Nudge:** arrow keys move the selection 1 mm, Shift+arrow 10 mm.
  - **Snap:** while dragging, the selection's box snaps to the paper's corners, edges, center and margin lines, and to other drawings' box edges, within 6 screen px. A thin guide shows the snap line. Hold Alt to turn snapping off.
- **Notification strip:** a slim bar across the top of the plate for problems and plot recovery (§4.6). It's never a popup.

### 2.5 Right panels
- **Jobs:**
  - An Import button, and one row per imported file showing its icon, name and page ("p. 2"), a check when placed at least once, and a ⚠ when it has issues (hover for the messages).
  - Double-click places the job. Dragging a row onto the plate places it at the drop point.
  - Right-click offers Place, Remove from list, and Show issues.
  - Selecting a placed drawing highlights its job row.
- **Pens:**
  - One row per pen color in plot order: the eye, the color swatch, the layer number and everyday name ("2 Red"), and the time.
  - The eye skips that color in this plot, leaving it out of plotting, times and trace.
  - If more than 12 colors are present, only the first 12 rows show, with "+N more", plus a warning at 10 or more (plan2-notes "Cap the color count").
- **Plotter:**
  - **Pen** type (Fine liner / Marker / Brush or paint pen).
  - **Height:** a slider (0–80) with the number, which moves the real pen live when it's down.
  - Raise pen / Lower pen, and Test mark.
  - The **jog pad:** four arrows plus a 1 mm / 10 mm step toggle.
  - The plotter's name and model, with **Plotter model…**.

### 2.6 Status bar
From left to right:
- the connection and model ("No plotter", "AxiDraw SE/A1", "Model unknown");
- power ("Power OK" / "Power adapter unplugged");
- Home ("Home set" / "Home not set");
- the pen X, Y and the cursor X, Y, in the current units;
- on the right, a **units** dropdown, in | mm | cm (remembered in settings).

## 3. Visual design (dark)

| Token | Value | Use |
|---|---|---|
| `--app-bg` | #1e1e1e | window background, canvas surround |
| `--panel` | #2b2b2b | menu bar, control bar, tools column, panels, status bar |
| `--panel-raised` | #353535 | panel headers, hovered rows, inputs |
| `--canvas` | #262626 | the plate |
| `--grid-minor` / `--grid-major` | #303030 / #3a3a3a | grid lines |
| `--line` | #444444 | dividers |
| `--text` / `--text-dim` / `--text-faint` | #e6e6e6 / #a8a8a8 / #707070 | text |
| `--paper` | #f4f3ef | the paper sheet |
| `--accent` | #3b8eea | selection, focus, active tool, Start |
| `--axis-x` / `--axis-y` | #e2504c / #5fa83a | Rhino axes |
| `--pen-cross` | #e0245e | live pen crosshair |
| `--danger` / `--warning` / `--success` | #e5534b / #d9a03b / #4caf68 | off-paper lines, warnings, status |

- **Type:** Segoe UI, at 12 px for controls and 11 px for the status bar and secondary text. Panel headers are 12 px semibold.
- **Sizes:** controls are 22 px high and tools 28 px squares. Radius is 3 px on controls and 0 on panels.
- **Effects:** none. No shadows except a 1 px focus ring and the menu and dialog drop shadow.
- **Icons:** Tabler Icons (MIT), outline, 16 px, bundled with the app (no CDN).
- **Lines:** on the paper, drawing lines are drawn 1.5 screen px wide in their pen color. Black pens draw as #1b1b1b, so they read on the light paper.

## 4. Behavior

### 4.1 Plotter
- **Connecting:** the page calls `plotter_scan` every 2 s while no plotter is connected. It also calls it after any `ok:false` reply that mentions the plotter.
- **Model unknown:** the status bar says so, and the tooltips on blocked controls point to **Plotter › Plotter model…**. That dialog lists the models with their sizes (spec §12) plus pen lift and label, and calls `plotter_identify`. The stored name is shown back to the student (plan2-notes).
- **Old firmware:** a one-time line in the notification strip: "This plotter's firmware is old. You'll be asked for the model on each laptop."
- **Set Home** is a two-click tool:
  - The first click calls `plotter_motors_off`, and the button stays pressed, labeled "Slide the pen to the HOME corner, then click again".
  - The second click calls `plotter_set_home`.
  - Esc cancels, and Home then stays not set.
- **Moves:** Move pen to point, the jog pad, Move pen Home, Raise/Lower pen and Test mark are **serialized**. One hardware call is in flight at a time, and slider changes send only the newest value after the previous reply (bridge.md).

### 4.2 Jobs and placement
- **Importing:** Import (dialog), or drop files on the window, calls `artwork_pages`. For more than one page, a small dialog asks which page. Then `job_import(path, page)` adds a row to Jobs.
  - Dropping onto the plate also places the job at the drop point.
  - Unsupported files (`.afdesign` and others) show their message in the strip.
- **Placing:** double-click puts the drawing's top-left corner at the paper's margin corner (the corner nearest Home, inset by the margin). Dragging places its top-left corner at the drop point. Both call `job_place(job_id, x, y)` at **scale 1, angle 0**.
- **Rotating:** the Rotate tool and the angle field turn a drawing about its center; the page computes the new top-left so the center stays put, then calls `piece_place`. Rotate 90° does the same in a quarter turn.
- **Rotate paper 90°** calls `paper_rotate()`. It swaps the paper's width and height and turns every placed drawing with it, so the layout keeps its place on the sheet.
- **Editing:** move, scale, rotate, nudge and typed values call `piece_place`. A drag sends one call when it ends, not on every frame. Duplicate calls `piece_duplicate`, and Delete calls `piece_delete`.
- **Fit to paper:** scales the selection down (never up) to fit inside the margins, centered.
- **Removing a job:** Remove from list removes the job **and its placed copies**, after a one-line confirmation in the strip ("Remove logo.ai and its 2 copies? Remove · Keep").

### 4.3 Pens and times
- **Refreshing:** after any placement or pen change, the page calls `job_colors`, debounced 300 ms, for the Pens panel.
- **Times:**
  - They come from `plot_prepare`. The page calls it, debounced 800 ms, whenever the plot is `idle`, something is placed, and the plotter's model is known. Home isn't needed. With no model, the chips show "—".
  - While it runs, the chips show "…". `plot_prepare` is never called while plotting.
- **Hiding a color:** the eye calls `set_pen_visible(color, on)`.

### 4.4 Plotting
| Plot state (bridge) | What the page shows |
|---|---|
| `idle`, `ready`, `done` | **Start** is enabled when §6 allows. Pause and Stop are greyed out. |
| `tracing` | The trace tool is pressed. **Stop** stops it (`plotter_stop`). |
| `load_pen` | The **pen-change dialog** (modal): the color swatch, "Put the **red** pen in the holder (2 of 3), then click Continue." Buttons: Continue, Cancel plot. |
| `plotting` | Pause and Stop are enabled. The crosshair follows `plot_progress`, lines already drawn darken, and the control bar shows time remaining. **Placed drawings are locked** (no moves) until the plot ends. |
| `pausing`, `homing` | The buttons are greyed out, with "Pausing…" or "Sending the pen Home…". |
| `paused`, `paused_at_home` | The control bar shows **Resume · Return Home · Cancel plot** (Return Home only when `paused`). |
| `reconnect` | The strip shows "Plotter disconnected. Plug it back in, then click Continue", with Continue and Cancel plot. |
| `slide_home` | The strip shows "Slide the pen to the corner next to the HOME label, then click It's in the corner", with It's in the corner and Cancel plot. |
| `not_connected` | The strip shows the message, with Retry and Cancel plot. |

- **Stop:** asks "Stop the plot? The pen lifts and this plot can't be resumed." (Stop · Keep plotting). On confirming, it calls `plot_pause`, then `plot_cancel` once the state is `paused`.
- **Done:** the strip says "Done! The pen is back Home." with **Plot another copy**, which calls Start again. The drawings stay on the paper.
- **Closing mid-plot:** `close_requested` opens the dialog "Stop the plot and close Rosetta Plotter?" (Stop and close · Keep plotting). On confirming, it calls `quit_confirmed`.
- **Laptop sleep:** while plotting, the status bar shows "Keep the laptop open while plotting."

### 4.5 Preview path and trace
- **Preview path:** draws the planned route from the `plot_prepare` summary. Pen-down moves show in their pen color and pen-up moves as faint dashes. An animated dot follows the route. The control bar shows a scrubber with play/pause and 1× / 4× / 16× speed. Esc or another tool ends it.
- **Trace outline:** calls `plot_trace`.

### 4.6 Problems and notifications
- Every `ok:false` reply shows its `message` as written in the strip, with **Details** (opens `details`) and **Copy diagnostics** (calls `diagnostics()`, then puts the text on the clipboard; if the clipboard is refused, the text is selected in a dialog so Ctrl+C works). Then the page calls `plot_status()` or `plotter_scan()` to refresh its state (bridge.md).
- The strip holds one message at a time, newest first. It closes on ✕, and on its own after 8 s for information-only messages.
- File issues stay on the job: the ⚠ on its row, plus the Job details in the control bar's tooltip.

### 4.7 Settings dialog (File › Settings)
- **General:**
  - units (in / mm);
  - margin;
  - grid on/off;
  - snapping on/off and snap distance;
  - skip white shapes (on by default, spec §6.3).
- **Advanced:** the engine options from `app_start().advanced_options`:
  - pen-up height, with Automatic as an option;
  - pen-down speed, with Automatic as an option;
  - pen-up speed;
  - acceleration;
  - pen raising and lowering speed;
  - the delays after raising and lowering;
  - path order;
  - hidden-line removal;
  - resolution.

  Each field is checked in the page first. The tab sends only what changed (`set_advanced` merges), and **Restore defaults** resets them all.

### 4.8 Keyboard and access
- Every control can be reached with Tab, and every icon button has an accessible name.
- Shortcuts are listed in Help › Keyboard shortcuts.
- When a text field has focus, shortcuts don't fire (except Esc).

## 5. Units
- **Inside the app** everything is mm. The page converts to the display units for fields, rulers, the status bar and the times panel.
- **Choices:** decimal inches (2 decimals, "3.25 in"), millimetres (1 decimal, "82.6 mm") and centimetres (2 decimals, "8.26 cm"), from View › Units or the status bar.
- **Typed values:** fields accept a unit suffix ("2 in", "2\"", "50 mm", "5 cm"). A bare number is read in the display units.
- **Checking:** the page checks ranges in the student's units before calling the bridge. A paper up to 2000 mm, a margin of 0–50 mm and so on are shown converted, so millimetre-only messages from Python stay a fallback.

## 6. Disabled controls and their tooltips

| Control | Greyed out when (first reason that applies is shown) |
|---|---|
| Start | No plotter connected · Model unknown (Plotter › Plotter model…) · Power adapter unplugged · Home not set (use Set Home) · Nothing placed on the paper · No pens visible · The plot is being prepared · A plot is running |
| Pause | Not plotting |
| Stop | Not plotting or tracing |
| Set Home | No plotter connected · Model unknown · A plot is running |
| Move pen to point, jog pad, Move pen Home, Raise or Lower pen, Test mark | No plotter connected · Model unknown · Home not set · A plot is running |
| Trace outline | No plotter · Home not set · Nothing placed · A plot is running |
| Preview path | Nothing placed · Times not ready yet |
| Arrange tools, control bar X/Y/W/H/angle | Nothing selected · A plot is running |
| Rotate paper 90° | A plot is running |
| Mark corner at pen | Home not set · A plot is running |

## 7. Changes to the Python layer (Plan 2a)

These come first in Plan 2b, each test-first.

- **Job queue (Session):**
  - `jobs`: loaded artwork with ids `job-N`, not yet placed.
  - `load_job(path, page)`: no placement.
  - `place_job(job_id, x, y) -> Piece` (scale 1, rotation 0); pieces carry `job_id`.
  - `remove_job(job_id)`: removes its pieces too.
  - `Session.add` and its use of `initial_placement` go away. (`compose.initial_placement` stays, for the CLI.)
- **Free rotation:** `Placement.rotation` becomes any angle in degrees (clockwise on screen). `geometry.place_point` and `rotated_size` handle any angle: the placement's (x, y) is the top-left of the rotated, scaled artwork frame's upright bounding box. The multiple-of-90 checks in `compose` and `session` go; finite angles are normalized to [0, 360). The CLI's job file accepts any angle.
- **Rotate paper:** `Session.rotate_paper()` swaps the paper's width and height and turns every piece 90° clockwise about the paper, mapping each piece's box (x, y, w, h) to (H − y − h, x, h, w), where H is the paper's height before the turn, and adding 90° to its angle. The bridge gets `paper_rotate()`, returning `material` and every piece's placement.
- **Hidden pens:** `Session.hidden_colors` is left out by `compose`; `compose_job` gets a `skip_colors` argument, alongside `skip_white`. The plot, times and trace all follow it.
- **Bridge (`api.py`, `payloads.py`, `docs/bridge.md`):**
  - **Added:**
    - `job_import(path, page)` returns `job` {id, name, path, page, width_mm, height_mm, issues, groups, preview}, the same shape as today's piece payload minus the placement;
    - `job_place(job_id, x, y)` returns `piece` {id, job_id, placement};
    - `job_remove(job_id)` returns `removed_pieces`;
    - `set_pen_visible(color, visible)`;
    - `job_list()`, for a page reload;
    - `paper_rotate()`.
  - **Changed:**
    - `piece_duplicate` returns the slim piece shape;
    - `job_colors` lists all colors with a `visible` flag;
    - `piece_place` accepts any angle.
  - **Removed:** `artwork_import`, replaced by `job_import`.
- **Tests:** the existing session, payload and api tests are updated to match, the full suite stays green, and the smoke window still passes.

## 8. Front-end architecture (`ui/`)

| Module | Responsibility |
|---|---|
| `src/bridge/contract.ts` | The TypeScript types for every method and event in `docs/bridge.md` |
| `src/bridge/client.ts` | Waits for `pywebviewready`, calls `window.pywebview.api`, unwraps `ok:false` into a typed error, and serializes hardware calls |
| `src/bridge/fake.ts` | A simulated plotter and backend with the same contract, for `npm run dev` in a browser and for tests |
| `src/state/store.ts` | One app state (machine, plot, jobs, pieces, pens, selection, view, units) with subscribe/update. Undo for placement edits |
| `src/geometry/` | Units and formatting, placement math (matching `rosetta.geometry.place_point`), bounding boxes, snapping, the reference point |
| `src/canvas/` | The plate: camera (pan/zoom), grid and rulers, reach and paper, pieces (one `<path>` per pen per piece), selection and handles, crosshair, preview animation |
| `src/ui/` | Lit components: menu bar, control bar, tools column, panels (Jobs, Pens, Plotter), status bar, strip, dialogs (pen change, page picker, plotter model, settings, confirmations, diagnostics) |
| `src/theme.css` | The dark design tokens (§3) and base control styles |
| `src/main.ts` | Builds the app, wires the bridge events and the keyboard shortcuts |

- **Build:** `npm run build` writes `ui/dist`, which `rosetta.app.main` already serves. `npm run dev` runs Vite with the fake bridge. Setting `ROSETTA_UI_URL=http://localhost:5173` makes the real window use the dev server against real Python.

## 9. Testing
- **Vitest, no browser:**
  - **Units** and parsing.
  - **Placement math**, checked against fixtures generated from `rosetta.geometry.place_point`, for 0°, 90°, 180°, 270° and several free angles (15°, 33.5°, 300°), at several scales; rotate-about-center and rotate-paper round trips.
  - **Snapping**, the reference point, bounding boxes, and the camera transforms.
  - **The store,** including undo.
  - **The serialization queue** in the bridge client.
- **Component tests (Vitest + jsdom), against the fake bridge:**
  - the disabled-reason logic (§6);
  - Jobs placing and removing;
  - the Pens eye;
  - the plot-state → UI mapping (§4.4), including the pen-change dialog, the strip actions, Stop's two-call sequence and closing mid-plot.
- **Python:** the pytest suite stays green and is extended for §7.
- **Smoke:** `scripts/smoke_window.py` also loads the built `ui/dist` and checks that the page reports ready.
- **By hand, on hardware:** spec §11.4, done through the new UI.

## 10. Not in this version
These are later updates, as in spec §9:
- reordering pen colors;
- hatch fill;
- a text tool;
- project files;
- "Send to plotter" from Illustrator or Affinity;
- two-corner alignment;
- a light theme.
