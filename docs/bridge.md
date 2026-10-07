# Rosetta Plotter bridge (Python ↔ page)

The student page talks to Python through pywebview's `js_api`, the `Api` class in `src/rosetta/app/api.py`. Plan 2b's front end is built on exactly this contract. Change the two together.

## Calling Python

- Wait for the window's `pywebviewready` event, then call `await window.pywebview.api.<method>(...args)`. Arguments are positional.
- Each call runs on its own Python thread, so the slow ones don't freeze the window. Show a spinner while awaiting them. The slow ones are `job_import`, `plot_prepare`, moves, `plot_trace` and `plotter_identify`.
- Every reply is `{"ok": true, ...fields}` or `{"ok": false, "message": "...", "details": "..."}`.
  - Show `message` exactly as written. It's plain language for students.
  - Put `details` behind a **Details** link.
  - An `ok: false` reply carries no state. Afterwards call `plot_status()` (or `plotter_scan()` in Steps 1–4) to redraw.
- **One hardware call at a time.** A move, pen move or trace that arrives while another is running is refused with "The plotter is still busy…". Serialize them: for the pen-height slider and the jog arrows, wait for the previous reply, then send only the newest value.
- **Stopped moves.** A trace or move stopped partway (Stop, the plotter's own button, a pulled cable) leaves `machine.state` `not_homed`: the student slides the pen Home again.
- **Units:** all lengths are millimetres in the machine frame.
  - (0, 0) is the Home corner. x runs along the rail, y toward the student.
  - The page converts to inches or centimetres only for display.
  - Size messages from Python are in mm too (e.g. custom paper "between 0 and 2000 mm", margin "from 0 to 50 mm"). Check what the student types in their own units first, so they rarely see these.
- **Whole numbers.** `pen_set`'s height and every Advanced value must be whole numbers: round slider and box values before sending.
- **Button labels.** Messages name buttons by their label, so keep the page's labels exactly: **Continue** (the `continue` and `reconnect` actions), **Resume**, **It's in the corner** (`rehomed`, and the Home step's button).

## Methods

### App
| Method | Arguments | Reply |
|---|---|---|
| `app_start()` | | `version`, `settings` {units, margin_mm, paper, advanced}, `models` [{number, name, travel}], `pen_types` [{key, label, speed}], `papers` [{key, label, short_mm, long_mm}], `advanced_options` {labels, ranges, choices}, `pen_down_max`, `machine`, `material`, `plot` |
| `set_units(units)` | `"in"`, `"mm"` or `"cm"` | |
| `set_advanced(values)` | {option: value}, only the options that changed (the rest keep their values); `null` means automatic for `pen_up` and `speed_pendown` | `advanced` (all options) |
| `diagnostics()` | | `text` for Copy diagnostics |
| `quit_confirmed()` | | pauses a running plot (pen up), lets go of the plotter, then closes the window. Can take several seconds; the reply may never arrive |

### Plotter (Step 1, Re-home, Steps 2 and 4)
While a plot is under way (`machine.state` is `plotting`), every call here that uses the plotter is refused, Re-home included.

| Method | Arguments | Reply |
|---|---|---|
| `plotter_scan()` | | `machine`. Call every 2 s while `machine.state` is `no_plotter` |
| `plotter_identify(model, penlift, label)` | model 1–7, penlift 1–3 (3 = brushless upgrade), label ≤ 40 characters | `machine`. `nickname` echoes what the plotter stored |
| `plotter_motors_off()` | | `machine` (`not_homed`: show the slide-Home instruction) |
| `plotter_set_home()` | | `machine` (`ready`, position [0, 0]) |
| `plotter_jog(dx, dy)` | mm | `machine` |
| `plotter_goto(x, y)` | mm from Home | `machine` |
| `plotter_pen(down)` | true or false | `machine` (needs `ready`) |
| `plotter_stop()` | | stops a trace or a Step 1–4 move in progress. It does not stop a plot: see Stopping a plot |
| `plotter_test_mark()` | | `machine` (a 10 mm line by the paper corner nearest Home, then Home) |
| `pen_set(pen_down, pen_type)` | a whole number 0–`pen_down_max`, a `pen_types` key | `machine`. Remembered for this plotter; a down pen moves at once. During a plot it's remembered for the next one but doesn't change the running plot |

### Material (Step 2)
| Method | Arguments | Reply |
|---|---|---|
| `material_set(size, orientation, custom_width_mm, custom_height_mm, x, y)` | `size` is a `papers` key or `"custom"`. `orientation` is `"landscape"` or `"portrait"`. Custom sizes are taken exactly as typed. `x`, `y` is the paper corner nearest Home | `material` |
| `material_mark_corner()` | | `material` with x, y = the pen's position (needs a homed plotter) |
| `set_margin(margin_mm)` | 0–50 | `margin_mm` |

### Jobs and placed drawings
| Method | Arguments | Reply |
|---|---|---|
| `artwork_choose()` | | `paths` (empty if cancelled) |
| `artwork_pages(path)` | | `pages`. Ask which page when it's more than 1 |
| `job_import(path, page)` | page counts from 0 | `job` (added to the Jobs list, not placed) |
| `job_list()` | | `jobs`, `pieces` (for a page reload) |
| `job_place(job_id, x, y)` | top-left corner, from the paper's corner, in mm | `piece` (scale 1, angle 0: never shrunk) |
| `job_remove(job_id)` | | `removed_pieces` (the copies that were on the paper) |
| `piece_place(piece_id, x, y, scale, rotation, scale_y)` | any angle in degrees, clockwise; `scale_y` optional (stretch) | `placement` |
| `piece_duplicate(piece_id)` | | `piece` (offset 10 mm) |
| `piece_delete(piece_id)` | | |
| `paper_rotate()` | | `material`, `paper` (the saved choice), `pieces` (all, turned with the paper) |
| `set_pen_visible(color, visible)` | `#rrggbb` | `hidden` (the hidden colors) |
| `set_skip_white(skip)` | | `skip_white` |
| `job_colors()` | | `colors` [{layer, color, name, lines, visible}] (`layer` is null for hidden pens), `ink_bbox`, `clipped`, `empty` |
| `new_plot()` | | clears the paper; the Jobs list stays (refused mid-plot) |

### Plot (Step 5)
| Method | Reply |
|---|---|
| `plot_prepare()` | `summary` (slow: plans every pen). Start and Trace are refused until it replies. If the drawing, paper, pen or plotter changes meanwhile, it fails and the plot goes back to `idle` |
| `plot_trace()` | `machine`. Returns when the trace ends; `plotter_stop()` ends it early |
| `plot_start()`, `plot_continue()`, `plot_pause()`, `plot_resume()`, `plot_home()`, `plot_cancel()`, `plot_reconnect()`, `plot_rehomed()`, `plot_retry()` | `plot`, `machine` |
| `plot_status()` | `plot`, `machine` |

- **Prepare again when the plot goes back to `idle`.** Any change to the drawing, paper, pen, Advanced options or plotter makes the prepared plot out of date. At rest the plot goes to `idle` at once; during a trace, a pen change, a pause or a plot it goes to `idle` when that ends (instead of `ready` or `done`, keeping its `message`). In the Plot step, call `plot_prepare()` whenever `plot.state` becomes `idle`.
- **Power.** The power adapter is checked before each run: Start, Continue, Resume, Return Home and Try again. When it's unplugged, the call is refused with a message, the plot keeps its state, and `machine.power_ok` is false.
- **`machine.state` is `plotting`** from Start until the plot is done or cancelled, through `load_pen`, `paused`, `reconnect`, `slide_home` and the rest.

The page shows one button per entry in `plot.actions`. Each action maps to a method:

| Action | Method |
|---|---|
| `trace` | `plot_trace` |
| `start` | `plot_start` ("Start", or "Plot another copy" when done) |
| `continue` | `plot_continue` ("Continue") |
| `pause` | `plot_pause` |
| `resume` | `plot_resume` ("Resume") |
| `home` | `plot_home` |
| `cancel` | `plot_cancel` |
| `reconnect` | `plot_reconnect` ("Continue") |
| `rehomed` | `plot_rehomed` ("It's in the corner") |
| `retry` | `plot_retry` |
| `stop` | `plotter_stop` (only offered while tracing) |

### Stopping a plot
There's no Stop while plotting. The page's Stop is: `plot_pause()`, wait for the `paused` state, then `plot_cancel()`. `plotter_stop()` only stops a trace or a Step 1–4 move.

## Shapes

- **machine**:
  - `state`: one of `no_plotter`, `needs_model`, `not_homed`, `ready`, `plotting`
  - also: `firmware`, `power_ok`, `model`, `model_name`, `penlift`, `label`, `nickname`, `old_firmware`, `pen_down`, `pen_type`
  - `position`: [x, y] only when `ready`, otherwise null
- **material**: `x`, `y`, `width`, `height`, `reach` [x, y] or null, `fits` (true, false, or null before a plotter is known)
- **job**: `id`, `name`, `path`, `page`, `width_mm`, `height_mm`, `issues` [{code, message, count}], `groups` [{color, name, white, lines}] (`lines` are flat lists [x0, y0, x1, y1, …] in artwork mm), `preview` (a `data:image/svg+xml;base64,…` URL for an SVG `<image>`, or null).
- **piece**: `id`, `job_id`, `placement` {x, y, scale, scale_y, rotation}.
- **Placement math:** the artwork is scaled on its own axes (`scale` across its width, `scale_y` down its height), turned clockwise by `rotation` degrees, and the top-left of its upright box sits at (x, y) from the paper's corner nearest Home. See `rosetta.geometry.place_point`.
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
| `files_dropped` | `paths`: call `artwork_pages` and `job_import` for each |
| `close_requested` | {}: the window was closed mid-plot. Ask "Stop the plot and close?", then call `quit_confirmed()` (show a spinner: it pauses the plot first) |

## Plot states

| State | Means |
|---|---|
| `idle` | nothing prepared, or the prepared plot went out of date: call `plot_prepare()` |
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
