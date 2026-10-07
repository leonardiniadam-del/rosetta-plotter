# Notes for Plan 2 (student app), collected from Plan 1 reviews

These came out of the code reviews while building the core (Plan 1). Each one is a requirement or a known limit the student UI has to handle.

## Plotting engine (`rosetta.engine.runner`)
- **Pause button timing.** Enable Pause only once a run has started. A `pause()` sent before the worker thread enters `run()` / `return_home()` is lost.
- **Run off the UI thread.** Call `estimate()` and `load_artwork()` on a worker thread, never the UI thread. EMS takes seconds on large files.
  - Never estimate while a plot is running, because the extra CPU load fights the plot's 30 ms move timing.
- **Treat any mid-run ERROR as position unknown.** Force a re-home (motors off, slide Home, `set_resume_origin_home`) before offering Resume, because the stored resume position can be stale.
- **Logging.** Configure logging so `rosetta.ems` at INFO lands in the app log (the Details / Copy diagnostics feature). EMS's own `logger.error` lines go to devnull in windowed builds.
- **Console streams.** Create every EMS object through `make_axidraw()`, or call `ensure_std_streams()` at app start, so a windowed build never has `sys.stderr` set to None.
- **Validate before calling the engine.** Check settings (pen-down 0–80, penlift 1–3) before calling the engine. `run()` reports invalid settings only as a generic ERROR.
- **Final progress sample (minor engine fix).** If `on_progress` blocks, `run()` blocks too, and the final sample can overlap a still-alive poller. Keep the UI callback non-blocking: post to the UI thread and return.

## Plotter identity
- **Show the stored name.** Echo the stored nickname back to the student after writing it. Labels made only of unsupported characters (CJK, emoji) become empty, leaving just e.g. `m3p2`.
- **Check the write result.** Always check `write_identity()`'s return value.

## Hardware checklist additions (Task 21 and later)
- **Gap on resume after a USB loss.** EMS keeps counting up to about 50 ms of moves sent to a dead port. Check whether a visible gap appears on resume, and back off a few mm if needed.
- **Modern Standby laptops.** Confirm `keep_awake` (ES_SYSTEM_REQUIRED and ES_DISPLAY_REQUIRED) keeps a Modern Standby laptop plotting with the lid open.
- **Resume with the same settings.** A resume assumes the same model, reordering and hiding settings as the original run. Store the settings alongside the resume data.

## Compose
- **Duplicating a piece.** `Placement` is frozen, so use `dataclasses.replace` when duplicating a piece.
- **Cap the color count.** Cap the number of pen colors shown to students (EMS documents layers 1–1000). Warn when a file has dozens of colors.

## For Plan 2b (from the Plan 2a final review)
Left as they are on purpose. The page-facing rules are in docs/bridge.md.
- **Lock navigation in the WebView.** pywebview injects `js_api` into any page the window navigates to. Keep the window on the app's own page and open every outside link in the system browser.
- **Drag and drop isn't smoke-tested.** `scripts/smoke_window.py` doesn't cover dropping files on the window; check it by hand.
- **Size messages are in mm.** Messages from Python name sizes in mm (custom paper "between 0 and 2000 mm", margin "from 0 to 50 mm"). The page should check what the student types in their own units first, so they rarely see these.
- **Error recovery could be finer later.**
  - An engine ERROR on a fresh run of pen 2 or later ends the whole plot (there's no resume point yet).
  - An ERROR during a resume falls back to the older resume point.
- **A Pause at the instant Return Home starts can be lost.** It's harmless: the pen just reaches Home.

## Visual direction (from Adam, 2026-10-07): Rhino 8 as the inspiration
Adam shared a Rhino 8 screenshot as the look for the app. Architecture students already know Rhino, so a familiar look lowers the learning curve. What to borrow:
- **Canvas.** A single Top-style view: a gray canvas with a fine grid and the world axes drawn from Home (red = X along the rail, green = Y toward the student). It shows the plotter's reach, the paper and the artwork. There's one view, not four viewports.
- **Instruction line.** Rhino's command prompt area at the top becomes the plain-language instruction line for the current step ("Slide the pen to the corner next to the HOME label…").
- **Pens panel.** A right-side panel styled like Rhino's Layers panel lists one row per pen color: swatch, everyday name, show/hide, plot order. This is where the color groups surface.
- **Tool column.** A slim left tool column with only a few tools: select/move, scale, rotate 90°, center on paper, trace outline. Nothing else.
- **Snapping.** A small Osnap-style panel snaps artwork to the paper's corners, edges, center and margins.
- **Status bar.** The bottom status bar shows the live pen X/Y, units (in/mm toggle), plotter connection and model, power OK, and grid snap.
Keep the spec's step bar, plain language and "Advanced" hiding. Rhino's look should carry the guided flow, not replace it.