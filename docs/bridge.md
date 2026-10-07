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
| `piece_place(piece_id, x, y, scale, rotation)` | rotation 0, 90, 180 or 270 | `placement` |
| `piece_duplicate(piece_id)` | | `piece` (offset 10 mm) |
| `piece_delete(piece_id)` | | |
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
