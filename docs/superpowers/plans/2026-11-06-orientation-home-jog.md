# Machine Orientation, Set Home on the Bar, Hold-to-Move: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the plate view match how the real plotter is mounted (eight orientations, remembered per plotter), add a Set Home button beside Start, and make the jog arrows keep moving while held.

**Architecture:** Orientation is a view-only 2×2 matrix (one of eight) folded into the plate's `Camera`. All drawing, hit-testing and dragging already go through `toScreen`/`toMachine`, so most of the plate follows for free. Placements, job files and plots stay in machine coordinates and never see the orientation. Python only stores the orientation code per plotter key and hands it to the page.

**Tech Stack:** Python 3.12 (pytest), TypeScript + Lit + Vite (vitest, FakeApi).

**Spec:** `docs/superpowers/specs/2026-11-06-orientation-home-jog-design.md` (amends `2026-10-07-rosetta-manager-ui-design.md`).

Run Python with `.\.venv\Scripts\python.exe -m pytest` from the repo root. Run UI tests with `npm test` in `ui/`. The `py -3.12` launcher is broken in this repo.

## Global Constraints

- The orientation is only a view: no placement, job file, prepared plot or plotted line changes with it.
- There are exactly eight orientation codes: `nw-h nw-v ne-h ne-v se-h se-v sw-h sw-v` (the screen corner Home sits in, then whether machine X runs **h**orizontally or **v**ertically on screen). Default `nw-h` = today's view.
- Saved per `Machine.profile_key()`. A keyed plotter with nothing saved gets `nw-h`. With no key, the last-used code on this laptop applies.
- Orientation can be changed any time except while a plot runs or is paused (the same rule as Rotate paper: `plotRunning`).
- Readouts stay in machine numbers. A drawing's X/Y is its box corner nearest HOME, W is along machine X, H along machine Y. Copy says "corner nearest HOME", never "top-left".
- No numbers or labels drawn on the plate.
- Jog pad and arrow-key nudges move in **screen** directions.
- Set Home button: "Set Home" at rest, "Confirm Home" (highlighted) while `homing`, same `disabledReason("setHome")`, hidden while paused.
- Hold-to-move: one step per tap; hold starts after 300 ms; at most one move in flight; stops on release, pointer leave/cancel or window blur, and when the position stops changing (reach).

## Review Focus

1. **Mirrored orientations (`nw-v`, `ne-v`, `se-v`, `sw-v`) with the Rotate tool:** the drawing must turn the way the mouse goes on screen. Test in Task 4.
2. **Selection outline and grid in a 90° view:** the outline must have positive width and height and sit on the drawing; the grid must cover the whole window. Tests in Task 4.
3. **Orientation arriving after the window has fitted (plotter plugged in later):** the plate must re-fit to the new orientation, not keep a stale camera. Test in Task 4.
4. **Releasing a held arrow while a move is still in flight:** no further move may be sent after the in-flight one returns. Test in Task 8.
5. **Esc during the orientation pick while Set Home is also armed:** Esc cancels the pick first and leaves homing alone. Test in Task 6.

---

### Task 1: Python stores the orientation per plotter

**Files:**
- Modify: `src/rosetta/app/settings.py` (Settings, `_from_json`)
- Modify: `src/rosetta/app/api.py` (`app_start`, `plotter_scan`, `plotter_identify`, new `set_orientation`, `_load_profile`)
- Test: `tests/test_settings.py`, `tests/test_api.py`

**Interfaces:**
- Produces: `ORIENTATIONS: tuple[str, ...]` and `DEFAULT_ORIENTATION_VIEW = "nw-h"` in `settings.py` (don't reuse the name `DEFAULT_ORIENTATION`, which is the paper's). `Settings.orientation: str = "nw-h"` (last used) and `Settings.orientations: dict[str, str]` (keyed by profile key).
- Produces bridge: `set_orientation(code) -> {"orientation": str}`; `app_start()["orientation"]`; `plotter_scan()` and `plotter_identify()` replies gain `"orientation": str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_settings.py`:
```python
def test_orientations_load_and_bad_ones_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"orientation": "se-v", "orientations": {"Wall": "ne-h", "Bad": "up", 3: "nw-h"}}))
    settings = SettingsStore(path).settings
    assert settings.orientation == "se-v"
    assert settings.orientations == {"Wall": "ne-h"}
    path.write_text(json.dumps({"orientation": "sideways"}))
    assert SettingsStore(path).settings.orientation == "nw-h"
```

`tests/test_api.py`:
```python
def test_orientation_is_remembered_per_plotter(tmp_path):
    ebb = _plotter()
    api, _sink = make_api(tmp_path, ebb)
    assert ok(api.app_start())["orientation"] == "nw-h"
    assert ok(api.plotter_scan())["orientation"] == "nw-h"
    assert ok(api.set_orientation("sw-v")) == {"orientation": "sw-v"}
    again, _sink = make_api(tmp_path, ebb)
    assert ok(again.plotter_scan())["orientation"] == "sw-v"

def test_orientation_without_a_plotter_is_the_last_used(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.set_orientation("ne-v"))
    again, _sink = make_api(tmp_path)
    assert ok(again.app_start())["orientation"] == "ne-v"
    assert ok(again.plotter_scan())["orientation"] == "ne-v"

def test_a_new_plotter_starts_in_the_default_orientation(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.set_orientation("ne-v"))           # no plotter: last-used only
    again, _sink = make_api(tmp_path, _plotter())
    assert ok(again.plotter_scan())["orientation"] == "nw-h"

def test_orientation_rejects_unknown_codes_and_never_touches_the_plot(tmp_path):
    api, _sink = make_api(tmp_path, _plotter())
    ok(api.plotter_scan())
    ok(api.plotter_set_home())
    _place(api, tmp_path)
    before = ok(api.plot_prepare())
    assert "error" in api.set_orientation("up")      # match the file's existing error-reply check
    ok(api.set_orientation("se-h"))
    assert ok(api.plot_prepare()) == before
```
(Use whatever `ok()`/error-shape helper the file already uses for refused calls; see `test_problems_come_back_in_plain_language`.)

- [ ] **Step 2: Run them and see them fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_settings.py tests/test_api.py -k orientation -v`
Expected: FAIL (no `orientation` key or method).

- [ ] **Step 3: Implement**

- `settings.py`: add the constants and the two fields. In `_from_json`, use `_choice` for `orientation` and filter `orientations` to string keys whose value is in `ORIENTATIONS`.
- `api.py`: add `def _orientation(self) -> str`: a keyed plotter gives `settings.orientations.get(key, "nw-h")`, and no key gives `settings.orientation`. `set_orientation(code)` raises `ValueError` on an unknown code, saves `settings.orientation = code` and, if keyed, `settings.orientations[key] = code`. It does **not** call `self._plot.invalidate()`. Add `"orientation": self._orientation()` to `app_start`, `plotter_scan` and `plotter_identify` replies.

- [ ] **Step 4: Run them and see them pass, then the whole Python suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/rosetta/app/settings.py src/rosetta/app/api.py tests/test_settings.py tests/test_api.py
git commit -m "feat(app): remember the plate orientation per plotter"
```

---

### Task 2: Orientation math and the oriented camera

**Files:**
- Create: `ui/src/geometry/orientation.ts`, `ui/src/geometry/orientation.test.ts`
- Modify: `ui/src/geometry/camera.ts`, `ui/src/geometry/camera.test.ts`

**Interfaces:**
- Produces in `orientation.ts`:
  - `type Corner = "nw" | "ne" | "se" | "sw"`; `type OrientationCode = \`${Corner}-${"h" | "v"}\``; `const ORIENTATIONS: OrientationCode[]` (the eight, in the order of Global Constraints); `const DEFAULT_ORIENTATION: OrientationCode = "nw-h"`.
  - `interface Orient { a: number; b: number; c: number; d: number }`: screen direction = `[a·mx + b·my, c·mx + d·my]`; every entry is −1, 0 or 1.
  - `orientMatrix(code: OrientationCode): Orient`
  - `machineToScreenDir(o: Orient, v: Point): Point` and `screenToMachineDir(o: Orient, v: Point): Point` (the transpose, since o is orthogonal)
  - `codeFromPicks(home: Corner, toward: Corner): OrientationCode | null` (null unless `toward` is next to `home`; `nw`/`ne` and `sw`/`se` are horizontal neighbours, `nw`/`sw` and `ne`/`se` vertical)
  - `neighbours(corner: Corner): [Corner, Corner]`
- Produces in `camera.ts`: `Camera` gains `orient: Orient`. `fitCamera(box, view, orient = orientMatrix("nw-h"), padding = 32)`. `toScreen`/`toMachine` apply the orient. `zoomAt`/`panBy` keep it. New `cameraMatrix(c: Camera): string` returns the SVG `matrix(...)` text: `matrix(s·a, s·c, s·b, s·d, x, y)`.

The matrices (machine +X and +Y as screen directions; Home lands in the named corner because the content lies at positive machine x and y):

| code | +X → | +Y → |
|---|---|---|
| nw-h | right | down |
| nw-v | down | right |
| ne-h | left | down |
| ne-v | down | left |
| se-h | left | up |
| se-v | up | left |
| sw-h | right | up |
| sw-v | up | right |

- [ ] **Step 1: Write the failing tests**

`orientation.test.ts`:
- `it.each(ORIENTATIONS)("%s puts Home in its corner")`: map the machine box corners `(0,0)` and `(100,50)` to screen dirs, and check that `(0,0)` is the extreme in the named corner (for `ne`: max screen x, min screen y).
- `it.each(ORIENTATIONS)("%s: h means X runs across")`: `machineToScreenDir(o, [1, 0])` has non-zero x exactly when the code ends in `-h`.
- `it.each(ORIENTATIONS)("%s round-trips directions")`: `screenToMachineDir(o, machineToScreenDir(o, [3, -7]))` equals `[3, -7]`.
- `codeFromPicks("ne", "se")` is `"ne-v"`; `codeFromPicks("sw", "se")` is `"sw-h"`; `codeFromPicks("nw", "se")` is `null`; `codeFromPicks("nw", "nw")` is `null`.
- For every code: the full table above, as exact expectations.

`camera.test.ts` (keep the existing tests and pass the default orient wherever a test builds a `Camera` literal):
- `it.each(ORIENTATIONS)` round-trip: `toMachine(c, toScreen(c, [12.5, -3]))` ≈ `[12.5, -3]` for a camera with scale 2.5 and offset (40, 70).
- `fitCamera({x:0,y:0,width:200,height:100}, {width:400,height:800}, orientMatrix("nw-v"))`: the fitted box's screen bounds are centred and the scale uses 100 across and 200 down (`scale === Math.min((400-64)/100, (800-64)/200)`).
- `cameraMatrix` for `ne-h`, scale 2, offset (10, 20) is `"matrix(-2 0 0 2 10 20)"`.

- [ ] **Step 2: Run and see them fail**

Run: `npm test -- orientation camera` (in `ui/`)
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `orientation.ts` and update `camera.ts`**

In `fitCamera`, map the box's four corners through the orient, take the screen-direction bounds, then fit as today.

- [ ] **Step 4: Run and see them pass, then `npm test` (everything) and `npx tsc --noEmit`**

Expected: all pass. Fix the type errors from `Camera` literals elsewhere by adding `orient: orientMatrix(DEFAULT_ORIENTATION)`.

- [ ] **Step 5: Commit**

```bash
git add ui/src/geometry
git commit -m "feat(ui): the eight plate orientations and an oriented camera"
```

---

### Task 3: Orientation in the bridge, store and App

**Files:**
- Modify: `ui/src/bridge/contract.ts`, `ui/src/bridge/fake.ts`, `ui/src/state/store.ts`, `ui/src/state/reasons.ts`, `ui/src/app/app.ts`
- Test: `ui/src/app/app.test.ts`, `ui/src/bridge/fake.test.ts`

**Interfaces:**
- Consumes: `OrientationCode`, `DEFAULT_ORIENTATION`, `ORIENTATIONS` (Task 2); bridge replies (Task 1).
- Produces:
  - contract: `AppStart.orientation: OrientationCode`; `plotter_scan`/`plotter_identify` return `Reply<{ machine: MachineStatus; orientation: OrientationCode }>`; `set_orientation(code: OrientationCode): Reply<{ orientation: OrientationCode }>`.
  - store: `AppState.orientation: OrientationCode` (initial `"nw-h"`).
  - reasons: a new `"orientation"` key, disabled with the existing RUNNING reason while `plotRunning(s)`.
  - app: `async setOrientation(code: OrientationCode): Promise<void>`. It optimistically updates the store, calls the bridge, and on failure restores the old value and reports through the existing `fail`/`attempt` path. The handlers for `app_start`, `plotter_scan` and `plotter_identify` copy `reply.orientation` into the store when it differs.
  - fake: keeps one `orientation` (default `"nw-h"`), returns it from `app_start`/`plotter_scan`/`plotter_identify`, logs `set_orientation`, and rejects unknown codes the way it rejects other bad input.

- [ ] **Step 1: Write the failing tests** (`app.test.ts`)

```ts
it("starts in the saved orientation and changes it", async () => {
  const { app, fake } = await startApp();
  expect(app.state.orientation).toBe("nw-h");
  await app.setOrientation("se-v");
  expect(app.state.orientation).toBe("se-v");
  expect(fake.called("set_orientation")).toEqual([["se-v"]]);
});

it("takes the plotter's orientation when it is found", async () => {
  const { app, fake } = await startApp();
  fake.orientation = "ne-h";        // as if this plotter's saved view came back
  await app.scan();
  expect(app.state.orientation).toBe("ne-h");
});

it("won't change orientation during a plot", async () => {
  const { app, fake } = await readyToPlot();
  await app.startPlot();
  await app.setOrientation("sw-h");
  expect(fake.called("set_orientation")).toEqual([]);
  expect(app.state.notice?.message).toBeTruthy();
});
```
(Match `scan`'s real name in `app.ts`; it's the method around line 236 that calls `plotter_scan`.)

- [ ] **Step 2: Run, see them fail. Step 3: implement. Step 4: `npm test` and `npx tsc --noEmit` pass.**

- [ ] **Step 5: Commit**

```bash
git add ui/src/bridge ui/src/state ui/src/app
git commit -m "feat(ui): orientation in the bridge, store and App"
```

---

### Task 4: The plate draws and interacts in the orientation

**Files:**
- Modify: `ui/src/ui/plate.ts`
- Test: `ui/src/ui/plate.test.ts`

**Interfaces:**
- Consumes: `Camera.orient`, `cameraMatrix`, `orientMatrix` (Task 2); `AppState.orientation` (Task 3).

What changes in `plate.ts`:
- `fit()` passes `orientMatrix(this.s.orientation)` to `fitCamera`. In `updated()` (or wherever the store change lands), if `this.s.orientation` differs from the orientation the camera was built for, re-fit to the paper.
- The world `<g transform>` uses `cameraMatrix(cam)`.
- `grid()` maps all four window corners through `toMachine` and takes min/max for x0/x1/y0/y1.
- `selection()` outlines: take `toScreen` of the box's two opposite corners and use `rectFrom` (from `canvas/interaction`) for x/y/width/height.
- Nothing else should need changing: move, scale, marquee, the pen tool, drop and the crosshair already convert through `toMachine`/`toScreen`, and `angleAt` is measured in machine space, so a rotate drag follows the mouse in mirrored views too. The tests below prove it.

- [ ] **Step 1: Write the failing tests** (`plate.test.ts`, using its existing drag helpers and JS-dispatched pointer events)

- `it.each(["ne-h", "sw-v", "se-v"])("in %s, dragging right on screen moves the drawing right on screen")`: place a drawing, set the orientation, drag +40 px on screen x, and expect the selection outline's screen x to grow by 40 (±1). Also check that the stored placement changed by `screenToMachineDir(orient, [40/scale, 0])`.
- "in nw-v the selection outline has positive size and covers the drawing's handles": the outline's width and height are > 0, and every handle lies on its edges.
- "in nw-v the grid covers the whole window": the min/max of the minor lines' coordinates span the window's machine bounds.
- "in sw-v the Rotate tool turns the drawing the way the mouse goes": a drag clockwise on screen around the selection's centre turns the drawing clockwise **on screen**. Check that the handle that started at the drawing's on-screen top moves to the on-screen right.
- "re-fits when the orientation changes after it has fitted": mount, fit, then `app.store.update({ orientation: "ne-v" })`. The paper's on-screen box is now centred and has the turned aspect ratio.
- "the plot is the same in every orientation": with a prepared plot, switching orientation leaves `app.state.summary` unchanged (the same object, or deep-equal).

- [ ] **Step 2: Run, see them fail. Step 3: implement. Step 4: `npm test` passes.**

- [ ] **Step 5: Commit**

```bash
git add ui/src/ui/plate.ts ui/src/ui/plate.test.ts
git commit -m "feat(ui): the plate draws in the plotter's orientation"
```

---

### Task 5: Jog pad and arrow nudges follow the screen; copy says "corner nearest HOME"

**Files:**
- Modify: `ui/src/app/app.ts` (`jog`), `ui/src/shortcuts.ts` (arrow nudge), `ui/src/ui/plotter-panel.ts` (pad labels), `ui/src/app/app.ts` and `ui/src/geometry/placement.ts` comments plus any user-facing "top-left" copy
- Test: `ui/src/app/app.test.ts`, `ui/src/ui/menus.test.ts` or the existing shortcut tests

**Interfaces:**
- Consumes: `screenToMachineDir`, `orientMatrix` (Task 2).
- Produces: `app.jog(dx: number, dy: number)` now takes **screen** directions (−1/0/1) and converts them with the current orientation before multiplying by `jogStep`. Its signature is unchanged. The arrow-key nudge converts the screen arrow the same way before `moveSelectionBy`.

- [ ] **Step 1: Failing tests**

```ts
it("jogs in screen directions", async () => {
  const { app, fake } = await startApp();
  await app.setHome(); await app.setHome();
  await app.setOrientation("ne-v");          // +X down, +Y left
  await app.jog(0, 1);                        // screen down
  expect(fake.called("plotter_jog")).toEqual([[1, 0]]);
  await app.jog(1, 0);                        // screen right = machine -Y
  expect(fake.called("plotter_jog").at(-1)).toEqual([0, -1]);
});
```
Plus a shortcut test: in `se-h`, ArrowRight with one drawing selected calls `moveSelectionBy(-1, 0)`. In `nw-h` the existing behaviour holds.

- [ ] **Step 2: Run, fail. Step 3: implement.** Pad aria-labels become "Move pen up", "Move pen left", "Move pen right", "Move pen down", with the title suffix " (on screen)". Replace "top-left" in user-visible strings with "corner nearest HOME"; comments can say the same.

- [ ] **Step 4: `npm test` passes. Step 5: Commit**

```bash
git add ui/src
git commit -m "feat(ui): jog and nudge move the way the screen shows"
```

---

### Task 6: Set orientation: the two-click pick

**Files:**
- Modify: `ui/src/state/store.ts`, `ui/src/app/app.ts`, `ui/src/ui/plate.ts`, `ui/src/shortcuts.ts`, `ui/src/ui/menubar.ts`, `ui/src/ui/tools.ts`, `ui/src/ui/icons.ts`, `ui/src/app/shortcut-help.ts`
- Test: `ui/src/app/app.test.ts`, `ui/src/ui/plate.test.ts`, `ui/src/ui/menus.test.ts`

**Interfaces:**
- Consumes: `Corner`, `codeFromPicks`, `neighbours` (Task 2); `setOrientation` and the `"orientation"` reason (Task 3).
- Produces:
  - store: `orienting: null | { home: Corner | null }`.
  - app: `startOrienting(): void` (blocked by reason `"orientation"`; sets `{ home: null }` and an info notice with `keep: true`, text `"Click the corner where HOME is on your plotter, as you face it."`); `pickCorner(corner: Corner): Promise<void>` (the first pick stores home and changes the notice to `"Click the corner the pen moves toward along X (along the rail)."`; the second pick, if it's a neighbour, calls `setOrientation(codeFromPicks(...))`, clears `orienting` and the notice; a non-neighbour is ignored); `cancelOrienting(): void`; `resetOrientation(): Promise<void>` (→ `setOrientation("nw-h")`).
  - plate: while `orienting` is set, it draws a pick marker (a small accent square, no text) at each candidate **screen** corner of the reach box (the paper box if no reach): all four, then only `neighbours(home)`, with the chosen home marked as pressed. It takes the screen bounding box of the reach through `toScreen` and names its corners by screen position. A left click within 12 px of a marker calls `pickCorner`. Other clicks do nothing while picking.
  - shortcuts: Esc cancels orienting **before** the homing and preview branches.
  - menu: View › "Set orientation…" (reason `"orientation"`) and "Reset orientation" (same reason, plus disabled with "Already the standard view." when the code is `nw-h`).
  - tools: a Plotter-group button "Set orientation (match how your plotter sits)", `pressed` while orienting. Icon: Tabler `outline/axis-x.svg` (or `compass.svg`; builder's pick, added to `icons.ts`).

- [ ] **Step 1: Failing tests**
- App: `startOrienting` → `pickCorner("ne")` → `pickCorner("se")` gives `set_orientation` `[["ne-v"]]`, `orienting` null, and the notice cleared.
- App: `pickCorner("nw")` then `pickCorner("se")` (not a neighbour) sends nothing and is still waiting for the second pick.
- Shortcut: with `homing: true` and orienting active, Esc clears `orienting` and leaves `homing` true (Review Focus 5).
- Plate: while orienting, four `.pick` markers; after one pick, two; a dispatched click on a marker's centre picks that corner.
- Menu: during a plot "Set orientation…" is disabled with the running reason.

- [ ] **Step 2: Run, fail. Step 3: implement. Step 4: `npm test` passes. Step 5: Commit**

```bash
git add ui/src
git commit -m "feat(ui): Set orientation by picking HOME and the X corner"
```

---

### Task 7: Set Home beside Start

**Files:**
- Modify: `ui/src/ui/plotbar.ts`
- Test: `ui/src/ui/plotbar.test.ts`

**Interfaces:**
- Consumes: `app.setHome()`, `s.homing`, `disabledReason("setHome", s)`.
- Produces: `PlotButton` gains `active?: boolean`, rendered as class `active` (accent outline, like a pressed tool). In the non-paused branch of `buttons()`, the first entry is `{ label: s.homing ? "Confirm Home" : "Set Home", iconName: "home", active: s.homing, reason: waiting ?? disabledReason("setHome", s), run: () => void app.setHome() }`, with the title from the tools column while homing: "Slide the pen to the HOME corner, then click again (Esc cancels)".

- [ ] **Step 1: Failing tests**
- "Set Home sits just left of Start": the button labels begin `["Set Home", "Start", "Pause", "Stop"]`.
- "it runs the two-click Set Home": click → label "Confirm Home" with class `active`, `fake.called("plotter_motors_off")` has length 1; click → back to "Set Home", and the machine state is `ready`.
- "it is greyed with the Set Home reason": with no plotter, `aria-disabled="true"`, and clicking shows `disabledReason("setHome", …)` as the notice.
- The existing paused test (`["Resume", "Return Home", "Cancel plot"]`) still passes unchanged.

- [ ] **Step 2: Run, fail. Step 3: implement. Step 4: `npm test` passes. Step 5: Commit**

```bash
git add ui/src/ui/plotbar.ts ui/src/ui/plotbar.test.ts
git commit -m "feat(ui): Set Home on the control bar, beside Start"
```

---

### Task 8: Hold an arrow to keep moving

**Files:**
- Modify: `ui/src/app/app.ts`, `ui/src/ui/plotter-panel.ts`
- Test: `ui/src/app/app.test.ts`, `ui/src/ui/widgets.test.ts` (or a new `plotter-panel.test.ts`)

**Interfaces:**
- Consumes: `app.jog` (Task 5, screen directions).
- Produces in `app.ts`:
  - `HOLD_DELAY_MS = 300`, `HOLD_MOVE_MM = 3` (exported; Adam tunes this on hardware).
  - `jogHold(dx: number, dy: number): void`: does one `jog(dx, dy)` at the current step straight away, then after `HOLD_DELAY_MS`, while still held, loops: send one `plotter_jog` of `HOLD_MOVE_MM` in that screen direction (converted as in Task 5), await it, and repeat. It stops when released, when the call fails, when `blocked("move")`, or when the returned position equals the previous one (reach).
  - `jogRelease(): void`: ends the hold; no new move is sent after the in-flight one returns.
- Produces in `plotter-panel.ts`: the four arrow buttons use `@pointerdown` (primary button only, calls `jogHold`, captures the pointer) and `@pointerup`/`@pointercancel`/`@lostpointercapture` → `jogRelease`. Keyboard activation (`click` with `event.detail === 0`) still does a single `jog`. A `window` `blur` listener (added in `connectedCallback`, removed in `disconnectedCallback`) calls `jogRelease`. A disabled button still explains its reason on pointerdown, as today.

- [ ] **Step 1: Failing tests** (vitest fake timers)

```ts
it("a tap moves one step", async () => {
  const { app, fake } = await homedApp();  // setHome twice
  app.jogHold(1, 0); app.jogRelease();
  await settle();
  vi.advanceTimersByTime(1000); await settle();
  expect(fake.called("plotter_jog")).toEqual([[1, 0]]);
});

it("holding keeps moving, one move at a time, until release", async () => {
  const { app, fake } = await homedApp();
  fake.jogDelayMs = 50;                     // add to the fake: plotter_jog resolves after this delay
  app.jogHold(1, 0);
  await vi.advanceTimersByTimeAsync(300 + 50 * 4);
  expect(fake.maxInFlight("plotter_jog")).toBe(1);   // add to the fake
  const sent = fake.called("plotter_jog").length;
  expect(sent).toBeGreaterThan(2);
  app.jogRelease();
  await vi.advanceTimersByTimeAsync(500);
  expect(fake.called("plotter_jog").length).toBeLessThanOrEqual(sent + 1);   // only the in-flight one finishes
});

it("stops by itself at the reach", async () => {
  const { app, fake } = await homedApp();
  fake.position = [fake.reach[0], 0];       // already at the far end of X; the fake clamps like Plotter.goto
  app.jogHold(1, 0);
  await vi.advanceTimersByTimeAsync(2000);
  expect(fake.called("plotter_jog").length).toBeLessThanOrEqual(2);
});
```
(Use the fake's real field names for position and reach, and add clamping to `fake.plotter_jog` if it doesn't clamp yet.) Add a panel test: a pointerdown/pointerup pair on "Move pen right" sends one jog, and Enter on the focused button sends one jog.

- [ ] **Step 2: Run, fail. Step 3: implement. Step 4: `npm test` passes. Step 5: Commit**

```bash
git add ui/src
git commit -m "feat(ui): hold a jog arrow to keep the pen moving"
```

---

### Task 9: Whole-app checks and a fresh preview build

**Files:** none new (the build output in `ui/dist`).

- [ ] **Step 1:** `.\.venv\Scripts\python.exe -m pytest -q` → all pass.
- [ ] **Step 2:** in `ui/`: `npm test` and `npx tsc --noEmit` → all pass; `npm run build` → succeeds.
- [ ] **Step 3:** `.\.venv\Scripts\python.exe scripts\smoke_window.py` and `.\.venv\Scripts\python.exe scripts\smoke_window.py --page` → PASS (the bridge method count rises by one, `set_orientation`; update the expected count if the script pins it).
- [ ] **Step 4:** In the browser preview (`npm run dev`, FakeApi), try every orientation from View › Set orientation…, drag, rotate and jog in one mirrored view, and take a screenshot for Adam.
- [ ] **Step 5:** Commit any count or fixture updates: `git commit -m "chore: smoke checks know set_orientation"`.
- [ ] **Hand to Adam:** the hardware check from the spec (set the real orientation, jog, Move pen to point), tune `HOLD_MOVE_MM` by feel, and rebuild the installer with `powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1` once he's happy.
