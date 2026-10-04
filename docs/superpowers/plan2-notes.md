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
