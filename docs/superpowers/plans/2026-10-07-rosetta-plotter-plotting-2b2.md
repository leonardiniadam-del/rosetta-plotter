# Rosetta Plotter Plan 2b-2: Plotting from the Window

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A student can plot from the Rosetta Plotter window: times per pen, Start / Pause / Stop, pen-change prompts, recovery from a pulled cable, Trace outline, Preview path and a Settings dialog. Before that, this plan fixes what the Plan 2b-1 final review found.

**Architecture:**
- **Part A (Tasks 1–5)** fixes the Plan 2b-1 window. It touches the number fields, placement ordering, dialogs and keys, the plate, and a set of small app fixes.
- **Part B (Tasks 6–15)** adds plotting:
  - The App class (`ui/src/app/app.ts`) gains the plotting actions, following the bridge contract in `docs/bridge.md`.
  - `FakeApi` gains a pretend plot, so every screen can be tested without hardware.
  - The plot's live progress goes in its own small store, so the 10-per-second progress events don't re-render the whole window.

**Tech Stack:**
- Python 3.12 + pywebview 6.2 (`src/rosetta/app/`), tested with pytest.
- Vite 8 + TypeScript 7 + Lit 3 (`ui/`), tested with Vitest 5 + jsdom.
- Tabler icons.

**Spec:** `docs/superpowers/specs/2026-10-07-rosetta-manager-ui-design.md` (cited as "spec §n"). **Contract:** `docs/bridge.md`.

**Not in this plan (Plan 2b-3):**
- snapping, undo/redo, rulers;
- scaling and rotating several drawings about the group's center;
- dock resizing;
- Help › Quick Start;
- the snapping options in Settings.

These menu items don't exist yet and stay out.

---

## Ground rules for every task

- **Repo:** `C:\Users\leona\Projects\rosetta-plotter`. Work on `main` and commit locally; **never push**. End every commit message with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  ```
- **Python:**
  - Use `.venv\Scripts\python.exe`; the `py -3.12` launcher is broken.
  - Run tests with `.venv\Scripts\python.exe -m pytest -q`. The suite (695 tests at the start) must stay green.
- **UI:** run these in `ui\`:
  - `npm test` (116 tests at the start), `npm run typecheck`, `npm run build`.
  - Run a new test file a few times to catch flaky timing: `npx vitest run src/path/file.test.ts`.
- **Never touch real hardware.** A plotter may be plugged into this laptop. `tests/conftest.py` blocks serial ports.
  - Don't run `python -m rosetta.app.main`, `rosetta-app.exe`, or the desktop shortcut.
  - The only real-window checks allowed are `.venv\Scripts\python.exe scripts\smoke_window.py` and `... smoke_window.py --page`. They use a stand-in plotter.
- **Files:**
  - PowerShell writes need `-Encoding UTF8`. Prefer the Edit/Write tools.
  - Keep non-ASCII characters (`›`, `°`, `…`, `×`) as UTF-8.
- **Student-facing text:**
  - Plain language.
  - **Never say top/bottom/upper/lower for physical corners.** Say "the corner nearest Home" or "the HOME corner".
  - Button names in messages must match the button labels exactly.
- **Test helpers** live in `ui/src/test/setup.ts`:
  - `startApp(fake?)` returns `{ app, fake }`: an `App` over `FakeApi`, with `colorsDelayMs: 0`.
  - `settle()` waits 5 ms.
  - `mount(tag)` adds an element to the page.
  - `shadow(el)` returns its shadow root.
  - The FakeApi plotter is an SE/A1 (model 5) that's connected after `start()`, in state `not_homed`. Two clicks on Set Home make it `ready`.
  - `app.importFiles()` imports `C:\Demo\site-plan.svg`, a 120 × 80 mm job with a black and a red group. `app.placeJob("job-1")` places it at the margin corner (6.35, 6.35) as `piece-1` and selects it.

## File map

| File | Change |
|---|---|
| `src/rosetta/app/session.py` | scale above 100× → `UserProblem` (Task 2) |
| `src/rosetta/app/api.py` | Custom paper's orientation flips on Rotate paper (Task 5); `advanced_options.defaults` (Task 6) |
| `src/rosetta/app/plotjob.py` | `PREPARE_FIRST` text (Task 6) |
| `src/rosetta/app/main.py` | dark loading background (Task 5); keep the window on the app's page (Task 14) |
| `scripts/smoke_window.py` | `--page` checks the shell rendered (Task 5) |
| `ui/src/ui/field.ts` | commit only typed changes (Task 1) |
| `ui/src/ui/strip.ts` | Details closes for a new notice (Task 1) |
| `ui/src/ui/controlbar.ts`, `statusbar.ts`, `plotter-panel.ts` | `live()` select values (Task 1); paper lock, plot area, preview scrubber (Tasks 9, 12) |
| `ui/src/app/app.ts` | ordered placement calls (Task 2); small fixes (Task 5); prepare, plot actions, preview, settings (Tasks 7, 8, 12, 13) |
| `ui/src/bridge/fake.ts` | test knobs `hold`/`failNext` (Task 2); pretend plot (Task 6) |
| `ui/src/bridge/contract.ts` | plot methods, summary, progress, advanced (Task 6) |
| `ui/src/state/store.ts`, `reasons.ts`, `selectors.ts` | plot state, reasons for start/pause/stop/preview/paper (Task 7) |
| `ui/src/state/plotting.ts` (new) | `formatDuration`, `overallFraction`, `AT_REST` (Task 7) |
| `ui/src/geometry/route.ts` (new) | the planned route: point at a time, path drawn so far (Task 11) |
| `ui/src/ui/plotbar.ts` (new) | pen time chips, total or time left, Start/Pause/Stop or Resume/Return Home/Cancel plot (Task 9) |
| `ui/src/ui/dialogs.ts` | model dialog fix, focus and Enter (Task 3); pen change and confirmations (Task 10); Settings (Task 13) |
| `ui/src/ui/plate.ts` | polish (Task 4); plot overlay (Task 11); preview path (Task 12) |
| `ui/src/ui/menubar.ts`, `tools.ts`, `jobs.ts`, `pens.ts`, `icons.ts`, `shortcuts.ts`, `app/shortcut-help.ts` | fixes (Tasks 3–5); plot commands (Task 14) |
| `ui/src/main.ts`, `ui/src/bridge/client.ts` | `waitForApi` fix, dev fallback (Task 5); fake events in dev (Task 6) |
| `docs/bridge.md`, the spec, `docs/superpowers/plan2-notes.md` | notes (Task 15) |

---

# Part A: fixes from the Plan 2b-1 final review

## Task 1: Number fields and dropdowns keep what they show

**Why:** Leaving a number field without typing re-commits the *rounded* display value. For example, X = 10.123 mm shown in inches moves to 10.16 mm, and a read-only A4 width turns the paper into Custom 296.926 mm.
- The `<select>`s use `?selected` on options, so after a refused change they keep showing the student's pick instead of the real state.
- The strip's Details stays open for the next notice.

**Files:**
- Modify: `ui/src/ui/field.ts` (`commit`)
- Modify: `ui/src/ui/controlbar.ts` (paper select), `ui/src/ui/statusbar.ts` (units select), `ui/src/ui/plotter-panel.ts` (pen type select)
- Modify: `ui/src/ui/strip.ts`
- Create: `ui/src/ui/field.test.ts`
- Test: `ui/src/ui/widgets.test.ts` (add the strip test)

- [ ] **Step 1: Write the failing field tests**

Create `ui/src/ui/field.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import "./field";
import { mount, shadow } from "../test/setup";
import type { RpField } from "./field";

async function field(props: Partial<RpField>) {
  const element = await mount<RpField>("rp-field");
  Object.assign(element, props);
  await element.updateComplete;
  const input = shadow(element).querySelector("input") as HTMLInputElement;
  const commits: number[] = [];
  element.addEventListener("commit", (e) => commits.push((e as CustomEvent<number>).detail));
  return { element, input, commits };
}

describe("rp-field", () => {
  it("leaving the box without typing commits nothing, even when the shown value is rounded", async () => {
    const { input, commits } = await field({ value: 10.123, units: "in" });
    input.dispatchEvent(new FocusEvent("focus"));
    input.dispatchEvent(new FocusEvent("blur"));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    expect(commits).toEqual([]);
  });

  it("commits what was typed", async () => {
    const { input, commits } = await field({ value: 10, units: "mm" });
    input.value = "1 in";
    input.dispatchEvent(new FocusEvent("blur"));
    expect(commits).toEqual([25.4]);
  });

  it("a read-only box never commits and shows its value again", async () => {
    const { input, commits } = await field({ value: 297, units: "mm", readonly: true });
    input.value = "5";
    input.dispatchEvent(new FocusEvent("blur"));
    expect(commits).toEqual([]);
    expect(input.value).toBe("297.0");
  });
});
```

- [ ] **Step 2: Run it and see the first test fail**

Run: `npx vitest run src/ui/field.test.ts`
Expected: FAIL on the first test (it commits `10.16`) and on the read-only test (it commits `5`).

- [ ] **Step 3: Fix `commit` in `field.ts`**

Replace the `commit` method with:

```ts
  private commit(input: HTMLInputElement): void {
    const shown = this.format();
    // Untouched text, or a box that can't be edited: nothing to send (the shown value is rounded).
    if (this.readonly || this.disabled || input.value.trim() === shown) {
      input.value = shown;
      this.invalid = false;
      return;
    }
    const value = this.parse(input.value);
    if (value === null) {
      this.invalid = true;
      input.value = shown;
      return;
    }
    this.invalid = false;
    if (Math.abs(value - this.value) > 1e-9) this.dispatchEvent(new CustomEvent("commit", { detail: value }));
    input.value = this.format();
  }
```

- [ ] **Step 4: Run the field tests: PASS**

Run: `npx vitest run src/ui/field.test.ts`

- [ ] **Step 5: Write the failing select and strip tests**

Add to `ui/src/ui/controlbar.test.ts`, inside `describe("control bar, nothing selected", …)`:

```ts
  it("the paper list shows the paper actually in use", async () => {
    const { app } = await startApp();
    const root = shadow(await mount("rp-controlbar"));
    const size = root.querySelector('select[aria-label="Paper size"]') as HTMLSelectElement;
    size.value = "a4"; // picked, but the change never reached Python
    app.store.update((s) => ({ paper: { ...s.paper } }));
    await (root.host as RpControlbarLike).updateComplete;
    expect(size.value).toBe("letter");
  });
```

At the top of that file add `type RpControlbarLike = HTMLElement & { updateComplete: Promise<unknown> };`.

Add to `ui/src/ui/widgets.test.ts` (add any imports it lacks: `"./strip"`, `startApp`, `mount`, `shadow`, `settle`):

```ts
describe("notification strip", () => {
  it("closes Details when a different notice arrives", async () => {
    const { app } = await startApp();
    const strip = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-strip");
    app.notify({ kind: "error", message: "First.", details: "trace one" });
    await strip.updateComplete;
    const details = Array.from(shadow(strip).querySelectorAll("button")).find((b) => b.textContent?.trim() === "Details") as HTMLButtonElement;
    details.click();
    await strip.updateComplete;
    expect(shadow(strip).querySelector("pre")?.textContent).toBe("trace one");
    app.notify({ kind: "error", message: "Second.", details: "trace two" });
    await strip.updateComplete;
    expect(shadow(strip).querySelector("pre")).toBeNull();
  });
});
```

- [ ] **Step 6: Run them and see them fail**

Run: `npx vitest run src/ui/controlbar.test.ts src/ui/widgets.test.ts`
Expected: the paper test sees `"a4"`; the strip test still finds a `<pre>`.

- [ ] **Step 7: Bind the selects' live value**

- In `controlbar.ts`, `statusbar.ts` and `plotter-panel.ts`, add `import { live } from "lit/directives/live.js";`.
- Add a `.value=${live(…)}` binding on each `<select>`, keeping the `?selected` on the options. Lit sets the select's value before its options exist on the first render; `?selected` covers that render, and `live()` covers later ones.
  - Paper size (`controlbar.ts`): `<select aria-label="Paper size" .value=${live(s.paper.size)} @change=…>`
  - Units (`statusbar.ts`): `<select aria-label="Units" .value=${live(units)} @change=…>`
  - Pen type (`plotter-panel.ts`): `<select aria-label="Pen type" .value=${live(m.pen_type)} @change=…>`

- [ ] **Step 8: Close Details for a new notice (`strip.ts`)**

Add a field and a `willUpdate` to `RpStrip`:

```ts
  private shown: unknown = null;

  protected willUpdate(): void {
    if (this.s.notice !== this.shown) {
      this.shown = this.s.notice;
      this.open = false;
    }
  }
```

- [ ] **Step 9: Run the whole UI suite and typecheck**

Run: `npm test` and `npm run typecheck`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add ui/src/ui/field.ts ui/src/ui/field.test.ts ui/src/ui/controlbar.ts ui/src/ui/controlbar.test.ts ui/src/ui/statusbar.ts ui/src/ui/plotter-panel.ts ui/src/ui/strip.ts ui/src/ui/widgets.test.ts
git commit -m "fix(ui): fields commit only typed changes; selects show the real state; Details closes for a new notice"
```

---

## Task 2: Placement changes reach Python in order, and scale stops at 100×

**Why:**
- `App.commitPlacement` previews first and never puts things back when Python refuses.
- pywebview runs each call on its own thread, so quick nudges can land out of order. A late reply then overwrites the newest preview.
- Scales above 100× reach Python and come back as "Something unexpected went wrong."

**Files:**
- Modify: `src/rosetta/app/session.py` (`_checked`)
- Modify: `tests/test_session.py` (the `test_bad_placements_are_refused` parameters, plus a new test)
- Modify: `ui/src/geometry/placement.ts` (export `MAX_SCALE`)
- Modify: `ui/src/bridge/fake.ts` (knobs `hold`, `failNext`; scale limit; missing piece on delete)
- Modify: `ui/src/app/app.ts`
- Test: `ui/src/app/app.test.ts`

- [ ] **Step 1: Write the failing Python test**

In `tests/test_session.py`:
- Remove `(0, 0, 1, 0, 1000)` from the `@pytest.mark.parametrize` list of `test_bad_placements_are_refused`.
- Add this test below it:

```python
def test_scaling_past_the_limit_is_explained(tmp_path):
    session, job = _session_with_job(tmp_path)
    piece = session.place_job(job.id, 0, 0)
    for scale, scale_y in ((101, None), (1, 1000)):
        with pytest.raises(UserProblem, match="Drawings can be scaled up to 10000%."):
            session.place(piece.id, 0, 0, scale, 0, scale_y)
```

- [ ] **Step 2: Run it: FAIL** (a ValueError is raised, not a UserProblem)

Run: `.venv\Scripts\python.exe -m pytest tests/test_session.py -q`

- [ ] **Step 3: Raise a UserProblem above the limit (`session.py`)**

Add `TOO_BIG = "Drawings can be scaled up to 10000%."` next to `GONE`. In `_checked`, replace the scale loop with:

```python
    for scale in (placement.scale, placement.scale if placement.scale_y is None else placement.scale_y):
        if not (math.isfinite(scale) and scale > 0):
            raise ValueError(f"Placement scale must be above 0: {placement}")
        if scale > MAX_SCALE:
            raise UserProblem(TOO_BIG)  # typed or dragged by the student
```

- [ ] **Step 4: Run the Python suite: PASS**

Run: `.venv\Scripts\python.exe -m pytest -q`

- [ ] **Step 5: Give FakeApi the same limit, plus two test knobs**

In `ui/src/geometry/placement.ts`, below `MIN_SIZE_MM`, add:

```ts
/** The largest scale Python accepts (session.MAX_SCALE): 100×, shown as 10000%. */
export const MAX_SCALE = 100;
```

In `ui/src/bridge/fake.ts`:
- Import `MAX_SCALE` alongside `pieceBox`.
- Add the constants `const GONE = "That drawing isn't on the paper anymore.";` and `export const TOO_BIG = "Drawings can be scaled up to 10000%.";`.
- Add these members to `FakeApi`:

```ts
  private readonly holds = new Map<string, Promise<void>>();
  private readonly failures = new Map<string, string>();

  /** Test knob: calls to `method` wait until the returned function is called. */
  hold(method: string): () => void {
    let release: () => void = () => {};
    this.holds.set(method, new Promise<void>((done) => (release = done)));
    return () => {
      this.holds.delete(method);
      release();
    };
  }

  /** Test knob: the next call to `method` is refused with `message`. */
  failNext(method: string, message: string): void {
    this.failures.set(method, message);
  }

  private async gate(method: string): Promise<Failure | null> {
    await this.holds.get(method);
    const message = this.failures.get(method);
    if (message === undefined) return null;
    this.failures.delete(method);
    return fail(message);
  }
```

Change `piece_place` and `piece_delete` to:

```ts
  async piece_place(pieceId: string, x: number, y: number, scale: number, rotation: number, scaleY: number) {
    this.log("piece_place", [pieceId, x, y, scale, rotation, scaleY]);
    const refused = await this.gate("piece_place");
    if (refused) return refused;
    const piece = this.pieces.find((p) => p.id === pieceId);
    if (!piece) return fail(GONE);
    const usable = [x, y, scale, rotation, scaleY].every(Number.isFinite) && scale > 0 && scaleY > 0;
    if (!usable) return fail("Something unexpected went wrong.", "ValueError: placement");
    if (scale > MAX_SCALE || scaleY > MAX_SCALE) return fail(TOO_BIG);
    piece.placement = { x, y, scale, scale_y: scaleY, rotation: normalizeAngle(rotation) };
    return ok({ placement: { ...piece.placement } });
  }

  async piece_delete(pieceId: string) {
    this.log("piece_delete", [pieceId]);
    if (!this.pieces.some((p) => p.id === pieceId)) return fail(GONE);
    this.pieces = this.pieces.filter((p) => p.id !== pieceId);
    return ok({});
  }
```

Also replace the other `"That drawing isn't on the paper anymore."` literals in the file with `GONE`.

- [ ] **Step 6: Write the failing App tests**

Add to `ui/src/app/app.test.ts`, inside `describe("App", …)`:

```ts
  it("quick nudges all land, in order, and a late reply never undoes a newer one", async () => {
    const { app, fake } = await withOneJob();
    const release = fake.hold("piece_place");
    void app.moveSelectionBy(1, 0);
    void app.moveSelectionBy(1, 0);
    void app.moveSelectionBy(1, 0);
    await settle();
    expect(app.state.pieces[0].placement.x).toBeCloseTo(9.35);
    release();
    await settle();
    const sent = fake.called("piece_place").map((args) => args[1] as number);
    expect(sent.at(-1)).toBeCloseTo(9.35);
    expect(sent.length).toBeLessThanOrEqual(3);
    expect(app.state.pieces[0].placement.x).toBeCloseTo(9.35);
    const { pieces } = await fake.job_list();
    expect(pieces[0].placement.x).toBeCloseTo(9.35);
  });

  it("puts a drawing back when Python refuses the change", async () => {
    const { app, fake } = await withOneJob();
    fake.failNext("piece_place", "Nope.");
    await app.setPlacement("piece-1", { ...app.state.pieces[0].placement, x: 50 });
    await settle();
    expect(app.state.pieces[0].placement.x).toBeCloseTo(6.35);
    expect(app.state.notice?.message).toBe("Nope.");
  });

  it("refuses to scale past 10000% without asking Python", async () => {
    const { app, fake } = await withOneJob();
    await app.setScale(150, 150);
    await settle();
    expect(fake.called("piece_place")).toEqual([]);
    expect(app.state.pieces[0].placement.scale).toBe(1);
    expect(app.state.notice?.message).toBe("Drawings can be scaled up to 10000%.");
  });
```

- [ ] **Step 7: Run them: FAIL**

Run: `npx vitest run src/app/app.test.ts`
Expected:
- the first test ends with x ≈ 7.35 or sends out of order;
- the second keeps x = 50;
- the third sends `piece_place`.

- [ ] **Step 8: Order the placement calls in `App`**

In `ui/src/app/app.ts`:
- Import `MAX_SCALE` from `../geometry/placement`.
- Add `export const TOO_BIG = "Drawings can be scaled up to 10000%.";` near `ONE_DRAWING`.
- Add these fields:

```ts
  /** Calls that change what's on the paper run one after another, in the order they were asked for. */
  private edits: Promise<unknown> = Promise.resolve();
  /** The newest placement still to be sent, per piece; only that one goes when the previous reply is in. */
  private readonly wanted = new Map<string, PlacementData>();
  private readonly sending = new Map<string, Promise<void>>();
```

Add these methods in the "Placing and editing drawings" section:

```ts
  private inOrder<T>(work: () => Promise<T>): Promise<T> {
    const run = this.edits.then(work);
    this.edits = run.catch(() => undefined);
    return run;
  }

  /** Ask Python for the Jobs list and the placed drawings again, after it refused a change. */
  async reload(): Promise<void> {
    try {
      const { jobs, pieces } = await this.client.call("job_list");
      const ids = new Set(pieces.map((p) => p.id));
      this.store.update((s) => ({ jobs, pieces, selection: s.selection.filter((id) => ids.has(id)) }));
    } catch (error) {
      this.fail(error);
    }
    this.refreshColors();
  }

  /** Send a piece's current placement to Python (the end of a drag, or a typed value). */
  commitPlacement(id: string): Promise<void> {
    const piece = this.state.pieces.find((p) => p.id === id);
    if (!piece) return Promise.resolve();
    const p = piece.placement;
    if (p.scale > MAX_SCALE || p.scale_y > MAX_SCALE) {
      this.explain(TOO_BIG);
      return this.inOrder(() => this.reload());
    }
    this.wanted.set(id, p);
    const busy = this.sending.get(id);
    if (busy) return busy;
    const sending = this.inOrder(() => this.sendPlacements(id));
    this.sending.set(id, sending);
    return sending;
  }

  private async sendPlacements(id: string): Promise<void> {
    try {
      for (let p = this.wanted.get(id); p; p = this.wanted.get(id)) {
        this.wanted.delete(id);
        try {
          const reply = await this.client.call("piece_place", id, p.x, p.y, p.scale, p.rotation, p.scale_y);
          // A newer placement is waiting: its own reply will be applied, not this older one.
          if (!this.wanted.has(id)) this.previewPlacement(id, reply.placement);
        } catch (error) {
          this.wanted.delete(id);
          this.fail(error);
          await this.reload();
          return;
        }
      }
      this.refreshColors();
    } finally {
      this.sending.delete(id);
    }
  }
```

Delete the old `async commitPlacement`. `setPlacement` stays as it is: preview, then `await this.commitPlacement(id)`.

- [ ] **Step 9: Run the other paper-changing calls through the same queue**

Wrap the bridge call in `this.inOrder(…)` in each of these:
- `placeJob`: `this.attempt(() => this.inOrder(() => this.client.call("job_place", jobId, at[0], at[1])))`
- `removeJob`'s inner `remove`: `this.inOrder(() => this.client.call("job_remove", jobId))`
- `rotatePaper`: `this.inOrder(() => this.client.call("paper_rotate"))`
- `duplicateSelection`: `this.inOrder(() => this.client.call("piece_duplicate", piece.id))`
- `deleteSelection`: `this.inOrder(() => this.client.call("piece_delete", id))`

- [ ] **Step 10: Run the UI suite (the new tests a few times) and typecheck: PASS**

Run: `npx vitest run src/app/app.test.ts` (3×), `npm test`, `npm run typecheck`

- [ ] **Step 11: Commit**

```bash
git add src/rosetta/app/session.py tests/test_session.py ui/src/geometry/placement.ts ui/src/bridge/fake.ts ui/src/app/app.ts ui/src/app/app.test.ts
git commit -m "fix: placement changes reach Python in order and are put back when refused; scale stops at 10000%"
```

---

## Task 3: Dialogs and keys

**Why:**
- The model dialog pre-selects model 1, so a student could save the wrong model without reading the label.
- Shortcuts fire while a dialog is open. Ctrl+I during the Pages dialog even replaces it and leaves its promise hanging.
- Esc closes a menu *and* deselects.
- Dialogs don't take focus, and Enter doesn't confirm them.
- Units menu items should be radio items.
- The pen eye's accessible name flips along with `aria-pressed`.

**Files:**
- Modify: `ui/src/ui/dialogs.ts`, `ui/src/shortcuts.ts`, `ui/src/ui/menubar.ts`, `ui/src/ui/pens.ts`
- Create: `ui/src/ui/dialogs.test.ts`
- Test: `ui/src/ui/menus.test.ts` (add)

- [ ] **Step 1: Write the failing tests**

Create `ui/src/ui/dialogs.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import "./dialogs";
import { handleShortcut } from "../shortcuts";
import { mount, settle, shadow, startApp } from "../test/setup";

type Lit = HTMLElement & { updateComplete: Promise<unknown> };

describe("plotter model dialog", () => {
  it("has no model chosen when the plotter's model is unknown, and Save explains", async () => {
    const { app, fake } = await startApp();
    fake.model = null;
    await app.scan();
    const dialogs = await mount<Lit>("rp-dialogs");
    app.openModelDialog();
    await dialogs.updateComplete;
    const root = shadow(dialogs);
    expect(root.querySelector('input[name="model"]:checked')).toBeNull();
    const save = root.querySelector("button.primary") as HTMLButtonElement;
    expect(save.getAttribute("aria-disabled")).toBe("true");
    save.click();
    await dialogs.updateComplete;
    expect(fake.called("plotter_identify")).toEqual([]);
    expect(root.querySelector(".hint")?.textContent).toBe("Choose the model on the plotter's label first.");
    const a2 = root.querySelector('input[name="model"][value="6"]') as HTMLInputElement;
    a2.checked = true;
    a2.dispatchEvent(new Event("change"));
    await dialogs.updateComplete;
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("plotter_identify")).toEqual([[6, 1, ""]]); // no stored label while the model is unknown
  });

  it("takes focus, and Enter confirms", async () => {
    const { app } = await startApp();
    const dialogs = await mount<Lit>("rp-dialogs");
    app.showDialog("about");
    await dialogs.updateComplete;
    await dialogs.updateComplete;
    expect(shadow(dialogs).activeElement?.tagName).toBe("BUTTON");
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await dialogs.updateComplete;
    expect(app.state.dialog).toBeNull();
  });
});

describe("shortcuts while a dialog is open", () => {
  it("only Esc works", async () => {
    const { app, fake } = await startApp();
    await app.importFiles();
    await app.placeJob("job-1");
    app.showDialog("about");
    const used = handleShortcut(app, new KeyboardEvent("keydown", { key: "Delete" }));
    handleShortcut(app, new KeyboardEvent("keydown", { key: "i", ctrlKey: true }));
    await settle();
    expect(used).toBe(false);
    expect(fake.called("piece_delete")).toEqual([]);
    expect(fake.called("artwork_choose")).toHaveLength(1); // only the import above
    expect(app.state.dialog?.kind).toBe("about");
  });
});
```

Add to `ui/src/ui/menus.test.ts` (use that file's existing imports; add `"./menubar"`, `mount`, `shadow`, `startApp` if missing):

```ts
describe("menus and Esc", () => {
  it("Esc closes an open menu without deselecting", async () => {
    const { app } = await startApp();
    await app.importFiles();
    await app.placeJob("job-1");
    const bar = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-menubar");
    (Array.from(shadow(bar).querySelectorAll("button.title")).find((b) => b.textContent?.trim() === "View") as HTMLButtonElement).click();
    await bar.updateComplete;
    const esc = new KeyboardEvent("keydown", { key: "Escape", bubbles: true });
    let reachedPage = false;
    window.addEventListener("keydown", () => (reachedPage = true), { once: true });
    document.body.dispatchEvent(esc);
    await bar.updateComplete;
    expect(shadow(bar).querySelector('[role="menu"]')).toBeNull();
    expect(reachedPage).toBe(false);
    expect(app.state.selection).toEqual(["piece-1"]);
  });

  it("Units are radio items", async () => {
    await startApp();
    const bar = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-menubar");
    (Array.from(shadow(bar).querySelectorAll("button.title")).find((b) => b.textContent?.trim() === "View") as HTMLButtonElement).click();
    await bar.updateComplete;
    const inches = Array.from(shadow(bar).querySelectorAll('[role="menu"] button')).find((b) => b.textContent?.includes("Inches"));
    expect(inches?.getAttribute("role")).toBe("menuitemradio");
  });
});
```

- [ ] **Step 2: Run them: FAIL**

Run: `npx vitest run src/ui/dialogs.test.ts src/ui/menus.test.ts`

- [ ] **Step 3: The model dialog starts with nothing chosen (`dialogs.ts`)**

- Add `static properties = { chosen: { state: true }, hint: { state: true } };` and `declare chosen: number | null; declare hint: string;`. In the constructor, set `this.chosen = null; this.hint = "";`.
- Add a `willUpdate` that resets them whenever a dialog opens, and an `updated` that moves focus into it:

```ts
  private lastDialog: unknown = null;

  protected willUpdate(): void {
    const dialog = this.s.dialog;
    if (dialog !== this.lastDialog && dialog?.kind === "model") {
      this.chosen = this.s.machine.model;
      this.hint = "";
    }
  }

  protected updated(): void {
    const dialog = this.s.dialog;
    if (dialog === this.lastDialog) return;
    this.lastDialog = dialog;
    if (!dialog) return;
    const first = this.renderRoot.querySelector<HTMLElement>(".dialog input, .dialog select, .dialog textarea, .dialog button");
    first?.focus();
  }
```

- In `modelForm()`:
  - Each radio gets `?checked=${m.number === this.chosen}` and `@change=${() => { this.chosen = m.number; this.hint = ""; }}`.
  - The Save button becomes:

```ts
        <button
          class="primary"
          aria-disabled=${this.chosen === null ? "true" : "false"}
          title=${this.chosen === null ? MODEL_FIRST : ""}
          @click=${() => (this.chosen === null ? (this.hint = MODEL_FIRST) : this.saveModel())}
        >Save</button>
```

  - Above the buttons add `${this.hint ? html`<p class="hint" role="alert">${this.hint}</p>` : nothing}`.
- Add `const MODEL_FIRST = "Choose the model on the plotter's label first.";` at module level, and in the styles add `.hint { color: var(--warning); }`.
- In `saveModel()`, use `const model = this.chosen; if (model === null) return;` in place of reading the checked radio.

- [ ] **Step 4: Enter confirms (`dialogs.ts` `onKey`)**

Replace `onKey` with:

```ts
  private onKey = (event: KeyboardEvent): void => {
    if (!this.s.dialog) return;
    if (event.key === "Escape") {
      event.stopPropagation();
      this.cancel();
      return;
    }
    const target = event.composedPath()[0];
    const inButtonOrText = target instanceof HTMLElement && ["BUTTON", "TEXTAREA"].includes(target.tagName);
    if (event.key === "Enter" && !inButtonOrText) {
      event.preventDefault();
      event.stopPropagation();
      this.renderRoot.querySelector<HTMLButtonElement>(".dialog button.primary")?.click();
    }
  };
```

- [ ] **Step 5: Shortcuts wait while a dialog is open (`shortcuts.ts`)**

In `handleShortcut`, right after the Escape block, add:

```ts
  if (app.state.dialog) return false; // a dialog is open: only Esc (above) does anything
```

- [ ] **Step 6: Esc closes a menu, and only that (`menubar.ts`)**

- Register `onKey` in the **capture** phase: `window.addEventListener("keydown", this.onKey, true)`, and remove it the same way.
- Change `onKey` to:

```ts
  private onKey = (event: KeyboardEvent): void => {
    if (event.key === "Escape" && this.open) {
      this.open = null;
      event.stopPropagation(); // the page's own Esc (deselect) doesn't run as well
    }
  };
```

- Give the `Item` interface `radio?: boolean`. The Units entries in `menus()` become `{ label: UNIT_NAMES[u], checked: s.units === u, radio: true, run: … }`.
- In `entry()`, the role becomes:

```ts
      role=${entry.checked === undefined ? "menuitem" : entry.radio ? "menuitemradio" : "menuitemcheckbox"}
```

- [ ] **Step 7: The eye keeps its name (`pens.ts`)**

Change the eye button's label to a fixed name, `aria-label=${`Plot the ${c.name} pen`}`, keeping `aria-pressed=${String(c.visible)}`. Pressed then means "plotted".

- [ ] **Step 8: Run the suite and typecheck: PASS**

Run: `npx vitest run src/ui/dialogs.test.ts` (3×), `npm test`, `npm run typecheck`. If an existing test in `dock.test.ts` looks for the old "Skip the … pen" label, update it to the new name.

- [ ] **Step 9: Commit**

```bash
git add ui/src/ui/dialogs.ts ui/src/ui/dialogs.test.ts ui/src/shortcuts.ts ui/src/ui/menubar.ts ui/src/ui/menus.test.ts ui/src/ui/pens.ts ui/src/ui/dock.test.ts
git commit -m "fix(ui): the model dialog starts unchosen; dialogs take focus and confirm on Enter; shortcuts wait for dialogs; Esc closes only the menu"
```

---

## Task 4: Plate polish

**Why:**
- Each icon svg carries two `class` attributes.
- Space pans even while a button has focus, so the button never gets pressed.
- Grabbing a handle a few pixels off makes the drawing jump.
- The inch grid's major lines fall every 1.25 in.
- The red off-paper pass draws a faint red edge under every on-paper line and doubles the drawing cost.
- The path cache is never cleared.
- Pieces aren't keyed.
- The plate has no visible focus ring.

**Files:**
- Modify: `ui/src/ui/icons.ts`, `ui/src/ui/plate.ts`
- Test: `ui/src/ui/plate.test.ts` (add), `ui/src/ui/widgets.test.ts` (add the icon test)

- [ ] **Step 1: Write the failing tests**

Add to `ui/src/ui/widgets.test.ts`:

```ts
import { ICON_NAMES, iconSvg } from "./icons";

describe("icons", () => {
  it("each icon has exactly one class attribute", () => {
    for (const name of ICON_NAMES) expect(iconSvg(name).match(/\sclass=/g)).toHaveLength(1);
  });
});
```

Add to `ui/src/ui/plate.test.ts`. Read the top of the file first and reuse its helpers for mounting the plate with a placed drawing and dispatching pointer events. If it has no helper that dispatches a `PointerEvent` at screen coordinates through the `svg`, add one like this:

```ts
function pointer(target: Element, type: string, x: number, y: number, extra: PointerEventInit = {}) {
  target.dispatchEvent(new PointerEvent(type, { clientX: x, clientY: y, button: 0, bubbles: true, composed: true, pointerId: 1, ...extra }));
}
```

Then add these tests:

```ts
  it("Space doesn't pan while a button has focus", async () => {
    await startApp();
    const plate = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-plate");
    const button = document.createElement("button");
    document.body.append(button);
    button.focus();
    const space = new KeyboardEvent("keydown", { key: " ", code: "Space", cancelable: true, bubbles: true });
    button.dispatchEvent(space);
    await plate.updateComplete;
    expect(space.defaultPrevented).toBe(false); // the button gets its Space
    expect(plate.dataset.tool).not.toBe("hand");
  });

  it("draws no red pass for lines that are on the paper", async () => {
    const { app } = await startApp();
    await app.importFiles();
    await app.placeJob("job-1");
    const plate = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-plate");
    await plate.updateComplete;
    const root = shadow(plate);
    expect(root.querySelector("mask#off-paper")).not.toBeNull();
    expect(root.querySelector("g[mask] path.off")).not.toBeNull();
  });
```

And a pure grid test in `ui/src/canvas/interaction.test.ts`:

```ts
import { GRID } from "./interaction";

  it("the inch grid has a stronger line every inch", () => {
    expect(GRID.in.minor * GRID.in.every).toBeCloseTo(25.4);
    expect(GRID.mm.minor * GRID.mm.every).toBe(50);
    expect(GRID.cm.minor * GRID.cm.every).toBe(50);
  });
```

- [ ] **Step 2: Run them: FAIL**

Run: `npx vitest run src/ui/widgets.test.ts src/ui/plate.test.ts src/canvas/interaction.test.ts`

- [ ] **Step 3: One class per icon (`icons.ts`)**

```ts
export function iconSvg(name: IconName): string {
  return ICONS[name]
    .trim()
    .replace(/\s+class="[^"]*"/, "")
    .replace(/^<svg/, '<svg class="icon" aria-hidden="true" focusable="false"');
}
```

- [ ] **Step 4: The grid per unit (`interaction.ts`, `plate.ts`)**

In `ui/src/canvas/interaction.ts` add:

```ts
import type { Units } from "../geometry/units";

/** Grid spacing in mm: a minor line, and a stronger one every `every` minor lines (spec §2.4). */
export const GRID: Record<Units, { minor: number; every: number }> = {
  in: { minor: 6.35, every: 4 }, // 1/4 in, stronger every inch
  mm: { minor: 10, every: 5 },
  cm: { minor: 10, every: 5 },
};
```

In `plate.ts`:
- Delete `GRID_MM` and import `GRID`.
- In `grid()`, use `const { minor, every } = GRID[this.s.units];` and draw `${lines(minor, "minor")}${lines(minor * every, "major")}`.

- [ ] **Step 5: Space only pans from the plate (`plate.ts` `onSpace`)**

Replace the start of `onSpace` so it ignores the key when focus is on any control other than the plate or the page:

```ts
  private onSpace = (event: KeyboardEvent): void => {
    if (event.code !== "Space" && event.key !== " ") return;
    const target = event.composedPath()[0];
    const onPlateOrPage = target === this || target === document.body || target === document.documentElement || target === window;
    if (!onPlateOrPage) return; // a focused button, field or menu gets its Space
```

Keep the rest of the method as it is (setting `spaceHeld`, `preventDefault`, `requestUpdate`).

- [ ] **Step 6: No jump when grabbing a handle (`plate.ts`)**

- Add `offset: Point` to the `scale` drag type.
- In `onDown`, when a handle is hit:

```ts
    if (handle && one && handles) {
      const corner = this.paperPoint(handles[handle] as Point);
      this.drag = { kind: "scale", id: one.id, handle, original: one.placement, offset: [corner[0] - paper[0], corner[1] - paper[1]] };
```

- In `onMove`, the scale branch uses the corner, not the pointer:

```ts
      const corner: Point = [paper[0] + drag.offset[0], paper[1] + drag.offset[1]];
      this.app.previewPlacement(drag.id, scaleFromHandle(job.width_mm, job.height_mm, drag.original, drag.handle, corner, event.shiftKey));
```

- [ ] **Step 7: Red only off the paper; keyed pieces; a clean cache; a focus ring (`plate.ts`)**

- Import `repeat` from `lit/directives/repeat.js`.
- In `render()`'s `<defs>`, add a mask beside the clip path, in the same machine units:

```ts
        <mask id="off-paper" maskUnits="userSpaceOnUse" x="-100000" y="-100000" width="200000" height="200000">
          <rect x="-100000" y="-100000" width="200000" height="200000" fill="white" />
          <rect x=${m.x} y=${m.y} width=${Math.max(0, clipRight - m.x)} height=${Math.max(0, clipBottom - m.y)} fill="black" />
        </mask>
```

- Replace the two piece lines with:

```ts
        <g mask="url(#off-paper)">${repeat(s.pieces, (p) => p.id, (piece) => this.piece(piece, "off"))}</g>
        <g clip-path="url(#printable)">${repeat(s.pieces, (p) => p.id, (piece) => this.piece(piece, "ink"))}</g>
```

- Add a `willUpdate` that drops cached paths for jobs that are gone:

```ts
  protected willUpdate(): void {
    const jobs = new Set(this.s.jobs.map((j) => j.id));
    for (const key of this.paths.keys()) if (!jobs.has(key.split("|")[0])) this.paths.delete(key);
  }
```

- In the styles add a focus ring:

```css
      :host(:focus-visible) {
        outline: 1px solid var(--accent);
        outline-offset: -1px;
      }
```

- [ ] **Step 8: Run the suite and typecheck: PASS**

Run: `npm test`, `npm run typecheck`

- [ ] **Step 9: Commit**

```bash
git add ui/src/ui/icons.ts ui/src/ui/plate.ts ui/src/ui/plate.test.ts ui/src/ui/widgets.test.ts ui/src/canvas/interaction.ts ui/src/canvas/interaction.test.ts
git commit -m "fix(ui): plate polish: red only off the paper, inch grid per inch, no handle jump, Space only on the plate, keyed pieces, focus ring"
```

---

## Task 5: Small fixes across the app

**Why:** This task covers the rest of the review's minor findings:
- Pen colors aren't refreshed after paper or model changes.
- "Show issues" uses plain `disabled`, and a job can't be removed from the keyboard.
- On Custom paper, Rotate paper keeps the old orientation.
- Linked W%/H% edits on a stretched drawing should scale both.
- The identify message shows the encoded nickname.
- `waitForApi` can grab a half-filled `pywebview.api`.
- Dev mode falls back to FakeApi inside the real window.
- The loading background flashes light.
- There's no old-firmware notice.
- The page doesn't check the margin and custom paper sizes in the student's units.
- The `--page` smoke check doesn't look at the shadow DOM.

**Files:**
- Modify: `ui/src/app/app.ts`, `ui/src/ui/jobs.ts`, `ui/src/ui/controlbar.ts`, `ui/src/bridge/client.ts`, `ui/src/main.ts`, `ui/src/bridge/fake.ts`
- Modify: `src/rosetta/app/api.py` (`paper_rotate`), `src/rosetta/app/main.py` (`BACKGROUND`), `scripts/smoke_window.py`
- Test: `ui/src/app/app.test.ts`, `ui/src/ui/dock.test.ts`, `ui/src/ui/controlbar.test.ts`, `ui/src/bridge/client.test.ts`, `ui/src/bridge/fake.test.ts`, `tests/test_api.py`

- [ ] **Step 1: Write the failing Python test**

Add to `tests/test_api.py`:

```python
def test_rotating_custom_paper_flips_its_orientation(tmp_path):
    api, _sink = make_api(tmp_path)
    ok(api.material_set("custom", "landscape", 500, 300))
    reply = ok(api.paper_rotate())
    assert reply["paper"] == {"size": "custom", "orientation": "portrait", "custom_width_mm": 300, "custom_height_mm": 500}
```

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py -q -k custom_paper_flips`. Expected: FAIL (the orientation stays landscape).

- [ ] **Step 2: Flip it (`api.py` `paper_rotate`)**

```python
            flipped = "portrait" if paper.orientation == "landscape" else "landscape"
            if paper.size == CUSTOM:
                settings.paper = PaperChoice(CUSTOM, flipped, material.width, material.height)
            else:
                settings.paper = PaperChoice(paper.size, flipped)
```

Run the Python suite: PASS.

- [ ] **Step 3: The same in FakeApi, with a test**

In `fake.ts` `paper_rotate`, replace the `if (this.paper.size === "custom") … else …` block with:

```ts
    const flipped = this.paper.orientation === "landscape" ? "portrait" : "landscape";
    const custom = this.paper.size === "custom";
    this.paper = {
      ...this.paper,
      orientation: flipped,
      custom_width_mm: custom ? this.material.width : null,
      custom_height_mm: custom ? this.material.height : null,
    };
```

Add to `ui/src/bridge/fake.test.ts`:

```ts
  it("rotating custom paper flips its orientation", async () => {
    const fake = new FakeApi();
    await fake.material_set("custom", "landscape", 500, 300, 0, 0);
    const reply = await fake.paper_rotate();
    expect(reply.ok && reply.paper).toEqual({ size: "custom", orientation: "portrait", custom_width_mm: 300, custom_height_mm: 500 });
  });
```

- [ ] **Step 4: Write the failing App tests**

Add to `ui/src/app/app.test.ts`:

```ts
  it("refreshes the pen colors after the paper changes", async () => {
    const { app, fake } = await withOneJob();
    await settle();
    const before = fake.called("job_colors").length;
    await app.setPaper("a4", "landscape");
    await settle();
    expect(fake.called("job_colors").length).toBeGreaterThan(before);
  });

  it("names the plotter by its stored label, and says if the plotter shortened it", async () => {
    const { app } = await startApp();
    await app.identify(5, 1, "PSU Lab");
    expect(app.state.notice?.message).toBe('Saved. This plotter is now named "PSU Lab".');
    await app.identify(5, 1, "Portland State Univ.");
    expect(app.state.notice?.message).toBe('Saved. This plotter is now named "Portland State U" (the plotter keeps a shorter name).');
  });

  it("says once when the plotter's firmware is old", async () => {
    const { app, fake } = await startApp();
    fake.oldFirmware = true;
    await app.scan();
    await app.scan();
    expect(app.state.notice?.message).toBe("This plotter's firmware is old. You'll be asked for the model on each laptop.");
    app.dismissNotice();
    await app.scan();
    expect(app.state.notice).toBeNull();
  });

  it("checks the margin in the student's units before asking Python", async () => {
    const { app, fake } = await startApp();
    await app.setMargin(60);
    expect(fake.called("set_margin")).toEqual([]);
    expect(app.state.notice?.message).toBe("The margin must be from 0 to 1.97 in.");
  });

  it("checks a custom paper size before asking Python", async () => {
    const { app, fake } = await startApp();
    await app.setUnits("cm");
    await app.setPaper("custom", "landscape", 2500, 300);
    expect(fake.called("material_set")).toEqual([]);
    expect(app.state.notice?.message).toBe("Paper width and height must be above 0 and at most 200.00 cm.");
  });
```

Python stores the label in the plotter's nickname, and the plotter may keep a shorter name. The message says what was stored, and adds a note when that differs from what was typed. For the fake to show both cases, give FakeApi these two knobs:
- `private labelStored: string | null = null;` — `status()` reports `label: model ? (this.labelStored ?? "Demo") : null`, and `plotter_identify` sets `this.labelStored = label.slice(0, 16)` (a stand-in for the plotter's limit).
- `oldFirmware = false;` — `status()` reports `old_firmware: this.connected && this.oldFirmware`.

- [ ] **Step 5: Run them: FAIL**

Run: `npx vitest run src/app/app.test.ts`

- [ ] **Step 6: Implement in `app.ts`**

1. **Pen colors after paper changes.** In `setPaper`, `movePaper`, `markCorner` and `identify` (after a successful reply), call `this.refreshColors();`.

2. **The identify message** (replacing the old one):

```ts
    const stored = this.state.machine.label ?? label;
    const shortened = stored !== label.trim() ? " (the plotter keeps a shorter name)" : "";
    this.notify({
      kind: "info",
      message: this.state.machine.old_firmware
        ? "Saved on this laptop. This plotter's firmware is old, so other laptops will ask for its model too."
        : `Saved. This plotter is now named "${stored}"${shortened}.`,
    });
```

3. **The old-firmware notice, once per session.** Add `private oldFirmwareSaid = false;` and change `setMachine`:

```ts
  setMachine(machine: MachineStatus): void {
    this.store.update((s) => ({ machine, homing: s.homing && machine.state === "not_homed" }));
    if (machine.old_firmware && !this.oldFirmwareSaid) {
      this.oldFirmwareSaid = true;
      this.notify({ kind: "info", message: "This plotter's firmware is old. You'll be asked for the model on each laptop." });
    }
  }
```

4. **Range checks in the student's units.** Import `formatLength` from `../geometry/units`, then add:

```ts
const MAX_MARGIN_MM = 50;
const MAX_PAPER_MM = 2000;
```

In `setMargin`, before the call:

```ts
    if (!(margin >= 0 && margin <= MAX_MARGIN_MM)) {
      return this.explain(`The margin must be from 0 to ${formatLength(MAX_MARGIN_MM, this.state.units, true)}.`);
    }
```

In `setPaper`, before the call:

```ts
    if (size === "custom") {
      const usable = (v: number | null) => v !== null && Number.isFinite(v) && v > 0 && v <= MAX_PAPER_MM;
      if (!usable(customWidth) || !usable(customHeight)) {
        return this.explain(`Paper width and height must be above 0 and at most ${formatLength(MAX_PAPER_MM, this.state.units, true)}.`);
      }
    }
```

- [ ] **Step 7: Linked W% / H% on a stretched drawing (`controlbar.ts`)**

While the link is on and the drawing is stretched (two scale fields showing), editing one scales both by the same ratio. Change the two `@commit` handlers:

```ts
                @commit=${(e: Commit) => (s.linkScale ? this.app.setScale(e.detail, p.scale_y * (e.detail / p.scale)) : this.app.setScale(e.detail, p.scale_y))}
```

and

```ts
                @commit=${(e: Commit) => (s.linkScale ? this.app.setScale(p.scale * (e.detail / p.scale_y), e.detail) : this.app.setScale(p.scale, e.detail))}
```

Add a test to `controlbar.test.ts`, in the "a drawing selected" block:

```ts
  it("with the link on, editing W% of a stretched drawing scales both", async () => {
    const { app, root } = await selected();
    await app.setScale(1, 2); // stretched: W% 100, H% 200
    await (root.host as HTMLElement & { updateComplete: Promise<unknown> }).updateComplete;
    commit(field(root, "W%"), 2);
    await settle();
    const p = app.state.pieces[0].placement;
    expect([p.scale, p.scale_y]).toEqual([2, 4]);
  });
```

If the existing `selected()` helper doesn't return `{ app, root }`, adjust it to.

- [ ] **Step 8: Jobs: "Show issues" explains; Delete removes a focused row (`jobs.ts`)**

The Show issues button:

```ts
      <button
        role="menuitem"
        aria-disabled=${job.issues.length === 0 ? "true" : "false"}
        title=${job.issues.length === 0 ? "This file has no issues." : ""}
        @click=${choose(() =>
          job.issues.length === 0
            ? this.app.explain("This file has no issues.")
            : this.app.notify({ kind: "warning", message: job.issues.map((i) => i.message).join(" ") }),
        )}
      >Show issues</button>
```

The row's keydown:

```ts
      @keydown=${(e: KeyboardEvent) => {
        if (e.key === "Enter") void this.app.placeJob(job.id);
        else if (e.key === "Delete") {
          e.stopPropagation(); // not the page's Delete (drawings on the paper)
          this.app.removeJob(job.id);
        }
      }}
```

Update the row's `title` to `` `${job.name}: double-click, or drag onto the paper, to place it. Delete removes it from the list.` ``. Add a test to `dock.test.ts`:

```ts
  it("Delete on a focused job row removes it", async () => {
    const { app } = await startApp();
    await app.importFiles();
    const jobs = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-jobs");
    await jobs.updateComplete;
    const row = shadow(jobs).querySelector(".row") as HTMLElement;
    row.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));
    await settle();
    expect(app.state.jobs).toEqual([]);
  });
```

- [ ] **Step 9: `waitForApi` waits for a filled bridge; dev falls back only in a plain browser**

In `client.ts`, replace `waitForApi`:

```ts
function filled(api: Api | undefined): api is Api {
  // pywebview fills window.pywebview.api in two steps: wait until the methods are there.
  return !!api && typeof (api as unknown as { app_start?: unknown }).app_start === "function";
}

/** The real bridge, once pywebview has injected it. Rejects after timeoutMs (in a plain browser, say). */
export function waitForApi(timeoutMs: number): Promise<Api> {
  const w = window as PyWindow;
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const look = () => {
      if (filled(w.pywebview?.api)) resolve(w.pywebview.api);
      else if (Date.now() - started >= timeoutMs) reject(new Error("The app's Python side didn't answer."));
      else window.setTimeout(look, 50);
    };
    look();
  });
}

/** Is this page inside the app's window (pywebview), rather than a plain browser? */
export function insideApp(): boolean {
  return "pywebview" in window;
}
```

Add to `client.test.ts`:

```ts
  it("waitForApi waits until the bridge has its methods", async () => {
    const w = window as unknown as { pywebview?: { api?: object } };
    w.pywebview = { api: {} };
    const waiting = waitForApi(1000);
    setTimeout(() => (w.pywebview = { api: { app_start: () => undefined } }), 60);
    const api = await waiting;
    expect(typeof (api as unknown as { app_start: unknown }).app_start).toBe("function");
    delete w.pywebview;
  });
```

In `main.ts` `pickApi`, wait longer inside the real window and fall back only in a plain browser:

```ts
async function pickApi(): Promise<Api> {
  const plainBrowser = import.meta.env.DEV && !insideApp();
  try {
    return await waitForApi(plainBrowser ? 1500 : 15000);
  } catch (error) {
    if (plainBrowser) return new FakeApi(); // `npm run dev` in a browser: the demo backend
    throw error;
  }
}
```

Import `insideApp` alongside `waitForApi`. pywebview creates `window.pywebview` before the API is filled, so `insideApp()` is true inside the window from the start.

- [ ] **Step 10: Dark loading background (`main.py`)**

```python
BACKGROUND = "#1e1e1e"  # the window background (spec §3 --app-bg), shown while the page loads
```

- [ ] **Step 11: The `--page` smoke check looks inside the shell (`scripts/smoke_window.py`)**

Find where the `--page` mode evaluates `window.rosettaReady` and the shell. Change the shell check's JavaScript to:

```js
(() => { const app = document.querySelector("rp-app"); const root = app && app.shadowRoot;
  return !!(root && root.querySelector("rp-plate") && root.querySelector("rp-menubar")); })()
```

so `shell` is true only when the window's parts actually rendered.

- [ ] **Step 12: Run everything**

Run:
- `npm test` (the new app tests 3×), `npm run typecheck`, `npm run build`;
- `.venv\Scripts\python.exe -m pytest -q`;
- `.venv\Scripts\python.exe scripts\smoke_window.py`;
- `.venv\Scripts\python.exe scripts\smoke_window.py --page`.

Expected: all pass, and `--page` prints `{'ready': True, 'shell': True}`.

- [ ] **Step 13: Commit**

```bash
git add src/rosetta/app/api.py src/rosetta/app/main.py tests/test_api.py scripts/smoke_window.py ui/src
git commit -m "fix: review minors: colors after paper changes, old-firmware notice, unit-aware checks, linked stretch, job keys, custom paper rotation, bridge wait, dark loading"
```


---

# Part B: plotting from the window

## Task 6: The plot in the bridge contract, Advanced defaults, and a pretend plot in FakeApi

**Why:** The page needs types for the plot methods and events (bridge.md "Plot"), the Advanced defaults for Settings › Restore defaults, and a FakeApi that plots, so every later task can be tested without hardware.

**Files:**
- Modify: `src/rosetta/app/api.py` (`app_start`: `advanced_options.defaults`), `src/rosetta/app/plotjob.py` (`PREPARE_FIRST`)
- Modify: `ui/src/bridge/contract.ts`, `ui/src/bridge/fake.ts`, `ui/src/main.ts`, `ui/src/test/setup.ts`
- Test: `tests/test_api.py`, `ui/src/bridge/fake.test.ts`

- [ ] **Step 1: Python: Advanced defaults and a page-era message**

Add to `tests/test_api.py`:

```python
def test_app_start_gives_the_advanced_defaults(tmp_path):
    defaults = ok(make_api(tmp_path)[0].app_start())["advanced_options"]["defaults"]
    assert defaults["accel"] == 75 and defaults["pen_up"] is None and defaults["hiding"] is False
```

Run it: FAIL (KeyError). In `api.py` `app_start`, add a line to `"advanced_options"`:

```python
                "defaults": dataclasses.asdict(Advanced()),
```

Import `Advanced` from `rosetta.engine.options` if `api.py` doesn't already. In `plotjob.py`, change `PREPARE_FIRST` to `"Wait a moment: the plot is still being prepared."`. The wizard's "Plot step" no longer exists, and the page only sees this message if it calls Start or Trace too early. Run the Python suite and fix any test that compares against the old text.

- [ ] **Step 2: Contract types (`contract.ts`)**

Add these types:

```ts
export type AdvancedValues = Record<string, number | boolean | null>;

export interface PlotRun {
  down: boolean;
  /** Flattened [x, y, t, x, y, t, …]: machine mm from Home, t = seconds from the start of this pen's run. */
  points: number[];
}

export interface PlotLayerSummary {
  layer: number;
  color: string;
  name: string;
  seconds: number;
  pendown_mm: number;
  path: PlotRun[];
}

export interface PlotSummary {
  layers: PlotLayerSummary[];
  total_seconds: number;
  ink_bbox: number[];
  warnings: string[];
}

/** The plot_progress event: about every 100 ms while drawing (bridge.md Events). */
export interface PlotProgress {
  layer: number;
  x: number;
  y: number;
  pendown_mm: number;
  fraction: number;
  seconds_left: number;
}
```

In `AppStart`:
- `settings.advanced` becomes `AdvancedValues`;
- `advanced_options` gains `defaults: AdvancedValues`.

Add `type PlotReply = Reply<{ plot: PlotStatus; machine: MachineStatus }>;` and these members to `Api`:

```ts
  set_advanced(values: AdvancedValues): Reply<{ advanced: AdvancedValues }>;
  set_skip_white(skip: boolean): Reply<{ skip_white: boolean }>;
  plot_prepare(): Reply<{ summary: PlotSummary }>;
  plot_trace(): MachineReply;
  plot_start(): PlotReply;
  plot_continue(): PlotReply;
  plot_pause(): PlotReply;
  plot_resume(): PlotReply;
  plot_home(): PlotReply;
  plot_cancel(): PlotReply;
  plot_reconnect(): PlotReply;
  plot_rehomed(): PlotReply;
  plot_retry(): PlotReply;
```

Change the existing `plot_status(): Reply<{ plot: PlotStatus; machine: MachineStatus }>;` to `plot_status(): PlotReply;`.

- [ ] **Step 3: Write the failing FakeApi tests**

Add to `ui/src/bridge/fake.test.ts`:

```ts
async function readyFake() {
  const fake = new FakeApi();
  const events: [string, unknown][] = [];
  fake.emit = (name, data) => events.push([name, data]);
  await fake.plotter_scan();
  await fake.plotter_set_home();
  await fake.job_import("C:\\Demo\\a.svg", 0);
  await fake.job_place("job-1", 10, 10);
  return { fake, events };
}

describe("FakeApi plotting", () => {
  it("prepares a plot with one layer per visible pen, in machine mm", async () => {
    const { fake } = await readyFake();
    const reply = await fake.plot_prepare();
    if (!reply.ok) throw new Error(reply.message);
    expect(reply.summary.layers.map((l) => l.name)).toEqual(["black", "red"]);
    const first = reply.summary.layers[0].path.find((run) => run.down);
    expect(first?.points.slice(0, 2)).toEqual([10, 10]); // the drawing's corner, from Home (paper at 0, 0)
    expect(reply.summary.total_seconds).toBeGreaterThan(0);
  });

  it("asks for each pen, plots, and finishes at Home", async () => {
    const { fake, events } = await readyFake();
    await fake.plot_prepare();
    await fake.plot_start();
    expect((events.at(-1)?.[1] as { state: string }).state).toBe("load_pen");
    await fake.plot_continue();
    fake.progress(0.5);
    expect(events.at(-1)?.[0]).toBe("plot_progress");
    fake.finishLayer();
    await fake.plot_continue();
    fake.finishLayer();
    const last = events.filter(([name]) => name === "plot_state").at(-1)?.[1] as { state: string; message: string };
    expect(last).toMatchObject({ state: "done", message: "Done! The pen is back Home." });
  });

  it("pauses at the next step, and cancels", async () => {
    const { fake } = await readyFake();
    await fake.set_pen_visible("#ff0000", false);
    await fake.plot_prepare();
    await fake.plot_start(); // one pen: plotting at once
    expect((await fake.plot_status()).ok && (await fake.plot_status() as { plot: { state: string } }).plot.state).toBe("plotting");
    await fake.plot_pause();
    await new Promise((done) => setTimeout(done, 5));
    await fake.plot_cancel();
    const status = await fake.plot_status();
    expect(status.ok && status.plot).toMatchObject({ state: "ready", message: "Plot cancelled." });
  });

  it("a change goes back to idle, and waits while plotting", async () => {
    const { fake } = await readyFake();
    await fake.plot_prepare();
    await fake.piece_place("piece-1", 20, 20, 1, 0, 1);
    expect(((await fake.plot_status()) as { plot: { state: string } }).plot.state).toBe("idle");
  });
});
```

Run: `npx vitest run src/bridge/fake.test.ts`. Expected: FAIL (the methods don't exist).

- [ ] **Step 4: Give FakeApi a pretend plot (`fake.ts`)**

- Import `applyMatrix` and `pieceMatrix` from `../geometry/placement`.
- Import the new types: `AdvancedValues`, `PenColor`, `PlotRun`, `PlotSummary`.
- Add these module constants:

```ts
const AT_REST = ["idle", "ready", "done"];
const PLOT_ACTIONS: Record<string, string[]> = {
  idle: [],
  ready: ["trace", "start"],
  tracing: ["stop"],
  load_pen: ["continue", "cancel"],
  plotting: ["pause"],
  pausing: [],
  paused: ["resume", "home", "cancel"],
  homing: ["pause"],
  paused_at_home: ["resume", "cancel"],
  reconnect: ["reconnect", "cancel"],
  slide_home: ["rehomed", "cancel"],
  not_connected: ["retry", "cancel"],
  done: ["start", "trace"],
};
const PEN_MM_S = 25; // drawing speed
const TRAVEL_MM_S = 100; // pen-up speed
const FINISH_FIRST = "Finish or cancel the current plot first.";
const PREPARE_FIRST = "Wait a moment: the plot is still being prepared.";
const NOT_NOW = "That can't be done right now.";

const ADVANCED_LABELS: Record<string, string> = {
  pen_up: "Pen-up height",
  speed_pendown: "Pen-down speed",
  speed_penup: "Pen-up speed",
  accel: "Acceleration",
  pen_rate_raise: "Pen raising speed",
  pen_rate_lower: "Pen lowering speed",
  pen_delay_up: "Delay after raising the pen",
  pen_delay_down: "Delay after lowering the pen",
  reordering: "Path order",
  hiding: "Hidden-line removal",
  resolution: "Resolution",
};
const ADVANCED_RANGES: Record<string, [number, number]> = {
  pen_up: [0, 100],
  speed_pendown: [1, 100],
  speed_penup: [1, 100],
  accel: [1, 100],
  pen_rate_raise: [1, 100],
  pen_rate_lower: [1, 100],
  pen_delay_up: [0, 1000],
  pen_delay_down: [0, 1000],
};
const ADVANCED_CHOICES: Record<string, number[]> = { reordering: [0, 1, 2, 4], resolution: [1, 2] };
export const FAKE_ADVANCED: AdvancedValues = {
  pen_up: null,
  speed_pendown: null,
  speed_penup: 75,
  accel: 75,
  pen_rate_raise: 75,
  pen_rate_lower: 50,
  pen_delay_up: 0,
  pen_delay_down: 0,
  reordering: 2,
  hiding: false,
  resolution: 1,
};
```

In `app_start`, the settings' `advanced` becomes `{ ...this.advanced }`, and `advanced_options` becomes:

```ts
      advanced_options: { labels: ADVANCED_LABELS, ranges: ADVANCED_RANGES, choices: ADVANCED_CHOICES, defaults: { ...FAKE_ADVANCED } },
```

Add these fields:

```ts
  /** Events, as Python sends them through window.rosettaEvent. Tests and `npm run dev` connect it to App.onEvent. */
  emit: (name: string, data: unknown) => void = () => {};
  private plotState = "idle";
  private plotMessage = "";
  private prepared: PlotSummary | null = null;
  private layerIndex = 0;
  private stale = false;
  private skipWhite = true;
  private advanced: AdvancedValues = { ...FAKE_ADVANCED };
  private autoFraction = 0;
```

`status()`'s `state` is `"plotting"` while a plot is under way, as in Python. Change its first line to:

```ts
    const plotting = !AT_REST.includes(this.plotState) && this.plotState !== "tracing";
    const state = !this.connected ? "no_plotter" : this.model === null ? "needs_model" : plotting ? "plotting" : this.homed ? "ready" : "not_homed";
```

Move the body of `job_colors` into a private `colorList(): PenColor[]`. `job_colors` then returns `ok({ colors: this.colorList(), ink_bbox: null, clipped: false, empty: … })`.

Add the plot machinery:

```ts
  private plotInfo(): PlotStatus {
    const layer = this.prepared?.layers[this.layerIndex];
    return {
      state: this.plotState,
      actions: [...(PLOT_ACTIONS[this.plotState] ?? [])],
      layer: this.layerIndex,
      layers: this.prepared?.layers.length ?? 0,
      color: layer?.color ?? null,
      name: layer?.name ?? null,
      message: this.plotMessage,
      details: "",
    };
  }

  private setPlot(state: string, message = ""): void {
    this.plotState = state;
    this.plotMessage = message;
    this.emit("plot_state", this.plotInfo());
  }

  /** The drawing, paper, pen or plotter changed: the prepared plot is out of date (bridge.md). */
  private invalidate(): void {
    if (!AT_REST.includes(this.plotState)) {
      this.stale = true;
      return;
    }
    this.prepared = null;
    this.layerIndex = 0;
    if (this.plotState !== "idle") this.setPlot("idle");
  }

  /** A plot or trace ended: at rest again, or idle if something changed meanwhile. */
  private rest(state: string, message = ""): void {
    if (this.stale) {
      this.stale = false;
      this.prepared = null;
      this.setPlot("idle", message);
    } else {
      this.setPlot(state, message);
    }
  }

  private plotReply() {
    return ok({ plot: this.plotInfo(), machine: this.status() });
  }

  private expect(...states: string[]): Failure | null {
    return states.includes(this.plotState) ? null : fail(NOT_NOW, `The plot is ${this.plotState}.`);
  }

  /** The planned plot: per visible pen, pen up to each line and down along it, then Home. */
  private summary(): PlotSummary {
    const origin: [number, number] = [this.material.x, this.material.y];
    const layers = this.colorList()
      .filter((c) => c.visible)
      .map((c) => {
        const runs: PlotRun[] = [];
        let at: [number, number] = [0, 0];
        let t = 0;
        let pendown = 0;
        const go = (down: boolean, points: [number, number][]) => {
          const flat = [at[0], at[1], Number(t.toFixed(3))];
          for (const p of points) {
            const d = Math.hypot(p[0] - at[0], p[1] - at[1]);
            t += d / (down ? PEN_MM_S : TRAVEL_MM_S);
            if (down) pendown += d;
            at = p;
            flat.push(Number(p[0].toFixed(2)), Number(p[1].toFixed(2)), Number(t.toFixed(3)));
          }
          runs.push({ down, points: flat });
        };
        for (const piece of this.pieces) {
          const job = this.jobs.find((j) => j.id === piece.job_id);
          if (!job) continue;
          const matrix = pieceMatrix(job.width_mm, job.height_mm, piece.placement, origin);
          for (const group of job.groups) {
            if (group.color !== c.color || (group.white && this.skipWhite)) continue;
            for (const line of group.lines) {
              const points: [number, number][] = [];
              for (let i = 0; i + 1 < line.length; i += 2) points.push(applyMatrix(matrix, [line[i], line[i + 1]]));
              if (points.length < 2) continue;
              go(false, [points[0]]);
              go(true, points.slice(1));
            }
          }
        }
        go(false, [[0, 0]]);
        return { layer: c.layer ?? 0, color: c.color, name: c.name, seconds: Number(t.toFixed(1)), pendown_mm: Number(pendown.toFixed(1)), path: runs };
      });
    const total = layers.reduce((sum, layer) => sum + layer.seconds, 0);
    return { layers, total_seconds: Number(total.toFixed(1)), ink_bbox: [0, 0, 0, 0], warnings: [] };
  }

  private askForPen(): void {
    const layers = this.prepared?.layers ?? [];
    const layer = layers[this.layerIndex];
    this.setPlot("load_pen", `Put the ${layer.name} pen in the holder (${this.layerIndex + 1} of ${layers.length}), then click Continue.`);
  }

  private runLayer(): void {
    const layers = this.prepared?.layers ?? [];
    this.setPlot("plotting", `Plotting the ${layers[this.layerIndex].name} pen (${this.layerIndex + 1} of ${layers.length}).`);
  }
```

Add the plot methods:

```ts
  async set_advanced(values: AdvancedValues) {
    this.log("set_advanced", [values]);
    for (const [name, value] of Object.entries(values)) {
      const label = ADVANCED_LABELS[name];
      if (!label) return fail("Something unexpected went wrong.", `ValueError: Unknown advanced option: ${name}`);
      if (name === "hiding") continue;
      if (value === null && (name === "pen_up" || name === "speed_pendown")) continue;
      if (typeof value !== "number" || !Number.isInteger(value)) return fail(`${label} must be a whole number.`);
      const choices = ADVANCED_CHOICES[name];
      if (choices && !choices.includes(value)) return fail(`${label} must be one of ${choices.join(", ")}.`);
      const range = ADVANCED_RANGES[name];
      if (range && !(value >= range[0] && value <= range[1])) return fail(`${label} must be from ${range[0]} to ${range[1]}.`);
    }
    this.advanced = { ...this.advanced, ...values };
    this.invalidate();
    return ok({ advanced: { ...this.advanced } });
  }

  async set_skip_white(skip: boolean) {
    this.log("set_skip_white", [skip]);
    this.skipWhite = skip;
    this.invalidate();
    return ok({ skip_white: skip });
  }

  async plot_prepare() {
    this.log("plot_prepare", []);
    const refused = await this.gate("plot_prepare");
    if (refused) return refused;
    if (!this.connected) return fail(NOT_CONNECTED);
    if (this.model === null) return fail(NEEDS_MODEL);
    if (!AT_REST.includes(this.plotState)) return fail(FINISH_FIRST);
    const summary = this.summary();
    if (summary.layers.length === 0) return fail("Nothing to plot: no lines land on the paper.");
    this.prepared = summary;
    this.layerIndex = 0;
    this.setPlot("ready");
    return ok({ summary });
  }

  async plot_trace() {
    this.log("plot_trace", []);
    const problem = this.problem(true);
    if (problem) return problem;
    if (!this.prepared || !["ready", "done"].includes(this.plotState)) return fail(PREPARE_FIRST);
    this.setPlot("tracing");
    await this.gate("plot_trace");
    this.position = [0, 0];
    this.rest("ready");
    return ok({ machine: this.status() });
  }

  async plot_start() {
    this.log("plot_start", []);
    const refused = (await this.gate("plot_start")) ?? this.problem(true);
    if (refused) return refused;
    if (!this.prepared || !["ready", "done"].includes(this.plotState)) return fail(PREPARE_FIRST);
    this.layerIndex = 0;
    this.position = [0, 0];
    if (this.prepared.layers.length > 1) this.askForPen();
    else this.runLayer();
    return this.plotReply();
  }

  async plot_continue() {
    this.log("plot_continue", []);
    const refused = this.expect("load_pen") ?? this.problem(true);
    if (refused) return refused;
    this.runLayer();
    return this.plotReply();
  }

  async plot_pause() {
    this.log("plot_pause", []);
    if (this.plotState === "plotting" || this.plotState === "homing") {
      this.setPlot("pausing", "Pausing...");
      setTimeout(() => {
        if (this.plotState === "pausing") this.setPlot("paused", "Paused. The pen is up.");
      }, 0);
    }
    return this.plotReply();
  }

  async plot_resume() {
    this.log("plot_resume", []);
    const refused = this.expect("paused", "paused_at_home") ?? this.problem(true);
    if (refused) return refused;
    this.runLayer();
    return this.plotReply();
  }

  async plot_home() {
    this.log("plot_home", []);
    const refused = this.expect("paused") ?? this.problem(true);
    if (refused) return refused;
    this.setPlot("homing", "Sending the pen Home.");
    setTimeout(() => {
      if (this.plotState !== "homing") return;
      this.position = [0, 0];
      this.setPlot("paused_at_home", "The pen is Home. Check or swap it, then click Resume.");
    }, 0);
    return this.plotReply();
  }

  async plot_cancel() {
    this.log("plot_cancel", []);
    const refused = this.expect("load_pen", "paused", "paused_at_home", "reconnect", "slide_home", "not_connected");
    if (refused) return refused;
    this.layerIndex = 0;
    this.rest("ready", "Plot cancelled.");
    return this.plotReply();
  }

  async plot_reconnect() {
    this.log("plot_reconnect", []);
    const refused = this.expect("reconnect");
    if (refused) return refused;
    this.setPlot("slide_home", "Slide the pen to the corner next to the HOME label and the USB port, then click It's in the corner.");
    return this.plotReply();
  }

  async plot_rehomed() {
    this.log("plot_rehomed", []);
    const refused = this.expect("slide_home");
    if (refused) return refused;
    this.setPlot("paused_at_home", "The pen is Home. Click Resume to carry on.");
    return this.plotReply();
  }

  async plot_retry() {
    this.log("plot_retry", []);
    const refused = this.expect("not_connected") ?? this.problem(true);
    if (refused) return refused;
    this.runLayer();
    return this.plotReply();
  }
```

Replace the existing `plot_status` with:

```ts
  async plot_status() {
    this.log("plot_status", []);
    return this.plotReply();
  }
```

Add the knobs that stand in for the plot actually running:

```ts
  /** Test and demo knob: progress through the current pen (0–1), as Python's plot_progress event reports it. */
  progress(fraction: number): void {
    const layers = this.prepared?.layers ?? [];
    const layer = layers[this.layerIndex];
    if (!layer || this.plotState !== "plotting") return;
    const down = layer.path.filter((run) => run.down).flatMap((run) => run.points);
    const count = Math.floor(down.length / 3);
    const index = Math.min(count - 1, Math.max(0, Math.floor(fraction * (count - 1))));
    const later = layers.slice(this.layerIndex + 1).reduce((sum, l) => sum + l.seconds, 0);
    this.emit("plot_progress", {
      layer: this.layerIndex,
      x: down[index * 3] ?? 0,
      y: down[index * 3 + 1] ?? 0,
      pendown_mm: layer.pendown_mm * fraction,
      fraction,
      seconds_left: layer.seconds * (1 - fraction) + later,
    });
  }

  /** Test and demo knob: the current pen finishes. The next one is asked for, or the plot is done. */
  finishLayer(): void {
    if (this.plotState !== "plotting") return;
    this.position = [0, 0];
    this.layerIndex += 1;
    if (this.layerIndex < (this.prepared?.layers.length ?? 0)) {
      this.askForPen();
    } else {
      this.layerIndex = 0;
      this.rest("done", "Done! The pen is back Home.");
    }
  }

  /** Test and demo knob: the USB cable is pulled mid-plot. */
  disconnect(): void {
    if (this.plotState === "plotting") this.setPlot("reconnect", "Plotter disconnected. Plug it back in, then click Continue.");
  }

  /** Demo (`npm run dev`): a running plot moves along by itself, a pen every few seconds. */
  autoplay(intervalMs = 100): () => void {
    const timer = setInterval(() => {
      if (this.plotState !== "plotting") return;
      this.autoFraction = Math.min(1, this.autoFraction + 0.02);
      this.progress(this.autoFraction);
      if (this.autoFraction >= 1) {
        this.autoFraction = 0;
        this.finishLayer();
      }
    }, intervalMs);
    return () => clearInterval(timer);
  }
```

Call `this.invalidate()` after a successful change in each of these:
- `piece_place`, `job_place`, `job_remove`, `piece_duplicate`, `piece_delete`, `paper_rotate`;
- `set_pen_visible`, `material_set`, `material_mark_corner`, `pen_set`, `plotter_identify`.

- [ ] **Step 5: Connect the fake's events in tests and in dev**

In `ui/src/test/setup.ts` `startApp`, right after creating the App: `fake.emit = (name, data) => app.onEvent(name, data);`.

In `ui/src/main.ts` `boot()`, keep the api in a variable. If it's a `FakeApi`, wire its events and start the demo:

```ts
  const api = await pickApi();
  const app = new App(new Store(initialState()), new Client(api));
  if (api instanceof FakeApi) {
    api.emit = (name, data) => app.onEvent(name, data);
    api.autoplay();
  }
```

- [ ] **Step 6: Run the suites: PASS**

Run: `npx vitest run src/bridge/fake.test.ts` (3×), `npm test`, `npm run typecheck`, `.venv\Scripts\python.exe -m pytest -q`

- [ ] **Step 7: Commit**

```bash
git add src/rosetta/app/api.py src/rosetta/app/plotjob.py tests ui/src/bridge ui/src/main.ts ui/src/test/setup.ts
git commit -m "feat: plot methods in the page's bridge contract, Advanced defaults, and a pretend plot in FakeApi"
```

---

## Task 7: Preparing the plot, and following the plot's state

**Why:**
- Times come from `plot_prepare`. The page calls it, debounced 800 ms, whenever the plot is `idle`, something is placed and the model is known (spec §4.3).
- Every `plot_state` event changes what the window shows.
- Progress events arrive about 10 times a second, so they go in their own small store.

**Files:**
- Create: `ui/src/state/plotting.ts`, `ui/src/state/plotting.test.ts`
- Modify: `ui/src/state/store.ts`, `ui/src/state/reasons.ts`, `ui/src/state/selectors.ts`, `ui/src/app/app.ts`
- Test: `ui/src/state/reasons.test.ts`, `ui/src/app/plot.test.ts` (new)

- [ ] **Step 1: Write the failing helper tests**

Create `ui/src/state/plotting.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { formatDuration, overallFraction } from "./plotting";

describe("plot helpers", () => {
  it("formats durations as m:ss, or h:mm:ss", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(59.6)).toBe("1:00");
    expect(formatDuration(250)).toBe("4:10");
    expect(formatDuration(3725)).toBe("1:02:05");
  });

  it("works out how far through the whole plot it is", () => {
    expect(overallFraction(100, null)).toBe(0);
    expect(overallFraction(100, { layer: 0, x: 0, y: 0, pendown_mm: 0, fraction: 0.5, seconds_left: 25 })).toBe(0.75);
    expect(overallFraction(0, { layer: 0, x: 0, y: 0, pendown_mm: 0, fraction: 1, seconds_left: 0 })).toBe(1);
  });
});
```

- [ ] **Step 2: Implement `ui/src/state/plotting.ts`**

```ts
/** Small facts about plotting that several parts of the page use. */
import type { PlotProgress } from "../bridge/contract";

/** The plot states where nothing is running (bridge.md "Plot states"). */
export const AT_REST = ["idle", "ready", "done"];

/** "4:10", or "1:02:05" past an hour. */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** How far through the whole plot (0–1), from the time left. */
export function overallFraction(totalSeconds: number, progress: PlotProgress | null): number {
  if (!progress) return 0;
  if (!(totalSeconds > 0)) return 1;
  return Math.min(1, Math.max(0, 1 - progress.seconds_left / totalSeconds));
}
```

Run: `npx vitest run src/state/plotting.test.ts` → PASS.

- [ ] **Step 3: State, selectors and reasons**

In `store.ts`, import `AdvancedValues` and `PlotSummary`, then add to `AppState`:

```ts
  /** The prepared plot: per-pen times and the planned path (null until plot_prepare replies). */
  summary: PlotSummary | null;
  preparing: boolean;
  /** Why the plot couldn't be prepared (shown on Start), or null. */
  prepareProblem: string | null;
  skipWhite: boolean;
  advanced: AdvancedValues;
  /** Preview path: playing or paused, and the speed. Null when it isn't showing. */
  preview: { playing: boolean; speed: 1 | 4 | 16 } | null;
```

In `initialState()`, set them to `summary: null, preparing: false, prepareProblem: null, skipWhite: true, advanced: {}, preview: null`. Add these `Dialog` variants:

```ts
  | { kind: "confirm"; title: string; message: string; confirm: string; cancel: string; run: () => void }
  | { kind: "settings" }
```

Give `Notice` an optional `source?: "plot"` (notices the plot puts up, which it takes down again).

In `selectors.ts`:
- Import `AT_REST` from `./plotting`.
- Make `plotRunning` read `return state.machine.state === "plotting" || !AT_REST.includes(state.plot.state);`.
- Add:

```ts
/** A dialog, or the pen-change dialog, has the window's attention: shortcuts wait. */
export function modalOpen(state: AppState): boolean {
  return state.dialog !== null || state.plot.state === "load_pen";
}
```

In `reasons.ts`, add the controls `"pause" | "stop" | "preview" | "paper"` to `Control`, plus these texts:

```ts
const PREPARING = "The plot is being prepared.";
const NOT_READY = "The plot isn't ready yet.";
const NOT_PLOTTING = "Not plotting.";
const NOT_PLOTTING_OR_TRACING = "Not plotting or tracing.";
```

Change `start`'s checks to (spec §6 order, then the prepare problems):

```ts
    start: [
      [machine === "no_plotter", NO_PLOTTER],
      [machine === "needs_model", NO_MODEL],
      [!s.machine.power_ok, NO_POWER],
      [machine === "not_homed", NO_HOME],
      [s.pieces.length === 0, NOTHING],
      [s.colors.length > 0 && s.colors.every((c) => !c.visible), NO_PENS],
      [plotRunning(s), RUNNING],
      [s.preparing, PREPARING],
      [s.prepareProblem !== null, s.prepareProblem ?? ""],
      [s.summary === null, NOT_READY],
    ],
```

Add the new controls:

```ts
    pause: [[!["plotting", "homing"].includes(s.plot.state), NOT_PLOTTING]],
    stop: [[!["plotting", "homing", "tracing"].includes(s.plot.state), NOT_PLOTTING_OR_TRACING]],
    preview: [
      [s.pieces.length === 0, NOTHING],
      [plotRunning(s), RUNNING],
      [s.preparing, PREPARING],
      [s.summary === null, "Times aren't ready yet."],
    ],
    paper: [[plotRunning(s), RUNNING]],
```

`trace` also needs the prepared plot. Append `[s.preparing || s.summary === null, NOT_READY]` to its list.

- [ ] **Step 4: Update the reasons test**

Add to `ui/src/state/reasons.test.ts`. Follow that file's way of building a state; if it has no helper, use `initialState()` plus overrides:

```ts
  it("Start waits for the plot to be prepared, and says why", () => {
    const ready = {
      ...initialState(),
      machine: { ...initialState().machine, state: "ready" as const, power_ok: true, model: 5 },
      pieces: [{ id: "piece-1", job_id: "job-1", placement: { x: 0, y: 0, scale: 1, scale_y: 1, rotation: 0 } }],
    };
    expect(disabledReason("start", { ...ready, preparing: true })).toBe("The plot is being prepared.");
    expect(disabledReason("start", { ...ready, prepareProblem: "Nothing to plot: no lines land on the paper." })).toBe(
      "Nothing to plot: no lines land on the paper.",
    );
    expect(disabledReason("start", ready)).toBe("The plot isn't ready yet.");
    expect(disabledReason("pause", ready)).toBe("Not plotting.");
    expect(disabledReason("stop", { ...ready, plot: { ...ready.plot, state: "tracing" } })).toBeNull();
  });
```

- [ ] **Step 5: Write the failing App tests**

Add a shared helper to `ui/src/test/setup.ts`; later tasks' tests use it too:

```ts
/** A homed plotter with one drawing placed (black and red pens), and the plot prepared. */
export async function readyToPlot(fake = new FakeApi()): Promise<{ app: App; fake: FakeApi }> {
  const started = await startApp(fake);
  const { app } = started;
  await app.setHome();
  await app.setHome();
  await app.importFiles();
  await app.placeJob("job-1");
  await settle();
  await settle();
  return started;
}
```

Create `ui/src/app/plot.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { App } from "./app";
import { Client } from "../bridge/client";
import { FakeApi } from "../bridge/fake";
import { initialState, Store } from "../state/store";
import { readyToPlot, settle, startApp } from "../test/setup";

describe("preparing the plot", () => {
  it("prepares once something is placed, and shows the times", async () => {
    const { app, fake } = await readyToPlot();
    expect(fake.called("plot_prepare").length).toBeGreaterThanOrEqual(1);
    expect(app.state.summary?.layers.map((l) => l.name)).toEqual(["black", "red"]);
    expect(app.state.plot.state).toBe("ready");
  });

  it("prepares again after a change", async () => {
    const { app, fake } = await readyToPlot();
    const before = fake.called("plot_prepare").length;
    await app.moveSelectionBy(10, 0);
    expect(app.state.summary).toBeNull();
    await settle();
    await settle();
    expect(fake.called("plot_prepare").length).toBe(before + 1);
    expect(app.state.summary).not.toBeNull();
  });

  it("never prepares without a model", async () => {
    const fake = new FakeApi();
    fake.model = null;
    const app = new App(new Store(initialState()), new Client(fake), { colorsDelayMs: 0, prepareDelayMs: 0, scanIntervalMs: 60_000 });
    fake.emit = (name, data) => app.onEvent(name, data);
    await app.start();
    await app.importFiles();
    await app.placeJob("job-1");
    await settle();
    expect(fake.called("plot_prepare")).toEqual([]);
    app.stop();
  });

  it("shows a prepare problem on Start, quietly", async () => {
    const fake = new FakeApi();
    fake.failNext("plot_prepare", "Nothing to plot: no lines land on the paper.");
    const { app } = await readyToPlot(fake);
    expect(app.state.prepareProblem).toBe("Nothing to plot: no lines land on the paper.");
    expect(app.state.notice).toBeNull();
  });

  it("keeps plot progress in its own store", async () => {
    const { app } = await readyToPlot();
    app.onEvent("plot_progress", { layer: 0, x: 5, y: 6, pendown_mm: 1, fraction: 0.1, seconds_left: 9 });
    expect(app.progress.state.value?.x).toBe(5);
  });
});
```

`startApp` must pass `prepareDelayMs: 0`. In `ui/src/test/setup.ts`, the App options become `{ colorsDelayMs: 0, prepareDelayMs: 0, scanIntervalMs: 60_000 }`.

- [ ] **Step 6: Run them: FAIL**

Run: `npx vitest run src/app/plot.test.ts`

- [ ] **Step 7: Implement in `app.ts`**

Imports: `PlotProgress` and `AdvancedValues` from the contract, and `AT_REST` from `../state/plotting`.

Options: `prepareDelayMs: number` in `AppOptions`, with a default of `800`.

Fields:

```ts
  /** The newest plot_progress event: its own store, so 10 updates a second re-render only what shows it. */
  readonly progress = new Store<{ value: PlotProgress | null }>({ value: null });
  private prepareTimer: ReturnType<typeof setTimeout> | null = null;
```

In `start()`, after the first `store.update`, add `advanced: start.settings.advanced` to that update. After `this.refreshColors();` add `this.schedulePrepare();`. In `stop()`, clear `prepareTimer` too.

`onEvent` gains:

```ts
    if (name === "plot_state") {
      this.onPlotState(data as PlotStatus);
    } else if (name === "plot_progress") {
      this.progress.update({ value: data as PlotProgress });
    } else if (name === "close_requested") {
      this.askToClose();
    } else if (name === "files_dropped") {
      // unchanged
    }
```

`askToClose` is written in Task 8. For now add it as a one-line stub that calls `void this.exit()`; Task 8 replaces it.

Add the prepare and plot-state methods:

```ts
  // Preparing the plot (spec §4.3).

  /** Plan the plot (times and path) a moment after the last change, whenever it's out of date. */
  schedulePrepare(): void {
    if (this.prepareTimer) clearTimeout(this.prepareTimer);
    this.prepareTimer = setTimeout(() => {
      this.prepareTimer = null;
      void this.prepare();
    }, this.options.prepareDelayMs);
  }

  private canPrepare(): boolean {
    const s = this.state;
    return s.plot.state === "idle" && !s.preparing && s.pieces.length > 0 && s.machine.model !== null && s.machine.state !== "no_plotter";
  }

  async prepare(): Promise<void> {
    if (!this.canPrepare()) return;
    this.store.update({ preparing: true, prepareProblem: null });
    try {
      const { summary } = await this.client.call("plot_prepare");
      this.store.update({ summary });
    } catch (error) {
      // Shown on Start, not in the strip: preparing is automatic. A change while preparing makes Python
      // go back to idle, and that plot_state event prepares again.
      const message = error instanceof BridgeError ? error.message : "The plot couldn't be prepared.";
      this.store.update({ summary: null, prepareProblem: message });
    } finally {
      this.store.update({ preparing: false });
    }
  }

  // The plot's state (spec §4.4).

  private onPlotState(plot: PlotStatus): void {
    const before = this.state.plot.state;
    this.store.update((s) => ({ plot, summary: plot.state === "idle" ? null : s.summary }));
    if (AT_REST.includes(plot.state)) this.progress.update({ value: null });
    if (plot.state === "idle") this.schedulePrepare();
    this.showPlotNotice(plot, before);
    if (AT_REST.includes(plot.state) && !AT_REST.includes(before)) void this.refreshPlot();
  }

  /** Ask Python where the plot and the plotter are (after a refused call, or when a plot ends). */
  async refreshPlot(): Promise<void> {
    try {
      const reply = await this.client.call("plot_status");
      this.setMachine(reply.machine);
      if (reply.plot.state !== this.state.plot.state) this.onPlotState(reply.plot);
    } catch {
      await this.scan();
    }
  }

  private showPlotNotice(plot: PlotStatus, before: string): void {
    // Filled in by Task 8.
  }
```

Changes trigger a prepare. In `refreshColors()`, add `this.schedulePrepare();` as its first line; every change that affects the plot already calls it. In `setMachine`, prepare again when the model becomes known or changes:

```ts
    const previous = this.state.machine;
    // … existing update …
    if (machine.model !== previous.model || (previous.state === "no_plotter") !== (machine.state === "no_plotter")) this.schedulePrepare();
```

The paper lock: in `setPaper`, `setOrientation`, `movePaper`, `markCorner` and `setMargin`, start with `if (this.blocked("paper")) return;`.

- [ ] **Step 8: Run: PASS**

Run: `npx vitest run src/app/plot.test.ts` (3×), `npm test`, `npm run typecheck`. Some older tests may expect `plot_status` or the reasons in their old form; update only what the new behavior explains.

- [ ] **Step 9: Commit**

```bash
git add ui/src
git commit -m "feat(ui): prepare the plot automatically, follow the plot's state and progress, lock the paper while plotting"
```

---

## Task 8: Start, Pause, Stop and the rest of the plot actions

**Why:** Spec §4.4.
- Start runs the prepared plot.
- Every `plot.actions` entry maps to a bridge method.
- Stop asks first, then pauses and cancels (bridge.md "Stopping a plot").
- The strip offers the recovery buttons.
- Done offers Plot another copy.
- Closing mid-plot asks first.

**Files:**
- Modify: `ui/src/app/app.ts`
- Test: `ui/src/app/plot.test.ts`

- [ ] **Step 1: Write the failing tests**

Add to `ui/src/app/plot.test.ts`:

```ts
describe("plotting", () => {
  it("asks for each pen and finishes with Plot another copy", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    expect(app.state.plot.state).toBe("load_pen");
    await app.plotAction("continue");
    expect(app.state.plot.state).toBe("plotting");
    fake.finishLayer();
    await app.plotAction("continue");
    fake.finishLayer();
    await settle();
    expect(app.state.plot.state).toBe("done");
    expect(app.state.notice?.message).toBe("Done! The pen is back Home.");
    expect(app.state.notice?.actions?.map((a) => a.label)).toEqual(["Plot another copy"]);
    expect(app.state.machine.state).toBe("ready");
  });

  it("explains instead of starting before Home", async () => {
    const { app, fake } = await startApp();
    await app.importFiles();
    await app.placeJob("job-1");
    await app.startPlot();
    expect(fake.called("plot_start")).toEqual([]);
    expect(app.state.notice?.message).toMatch(/^Home not set/);
  });

  it("Stop asks, then pauses and cancels", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    expect(app.state.plot.state).toBe("plotting");
    app.stopPlot();
    expect(app.state.dialog).toMatchObject({ kind: "confirm", title: "Stop the plot?", confirm: "Stop", cancel: "Keep plotting" });
    const dialog = app.state.dialog;
    if (dialog?.kind === "confirm") dialog.run();
    await settle();
    await settle();
    expect(fake.called("plot_pause")).toHaveLength(1);
    expect(fake.called("plot_cancel")).toHaveLength(1);
    expect(app.state.plot.state).toBe("ready");
    expect(app.state.notice?.message).toBe("Plot cancelled.");
  });

  it("Stop during a trace stops the trace without asking", async () => {
    const { app, fake } = await readyToPlot();
    const release = fake.hold("plot_trace");
    void app.trace();
    await settle();
    expect(app.state.plot.state).toBe("tracing");
    app.stopPlot();
    expect(app.state.dialog).toBeNull();
    expect(fake.called("plotter_stop")).toHaveLength(1);
    release();
    await settle();
  });

  it("a pulled cable shows Continue and Cancel plot in the strip", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    fake.disconnect();
    expect(app.state.notice?.message).toBe("Plotter disconnected. Plug it back in, then click Continue.");
    expect(app.state.notice?.actions?.map((a) => a.label)).toEqual(["Continue", "Cancel plot"]);
    app.state.notice?.actions?.[0].run();
    await settle();
    expect(app.state.plot.state).toBe("slide_home");
    expect(app.state.notice?.actions?.map((a) => a.label)).toEqual(["It's in the corner", "Cancel plot"]);
    app.state.notice?.actions?.[0].run();
    await settle();
    expect(app.state.plot.state).toBe("paused_at_home");
    expect(app.state.notice).toBeNull();
  });

  it("closing mid-plot asks first", async () => {
    const { app, fake } = await readyToPlot();
    app.onEvent("close_requested", {});
    expect(app.state.dialog).toMatchObject({ kind: "confirm", title: "Stop the plot and close Rosetta Plotter?", confirm: "Stop and close" });
    const dialog = app.state.dialog;
    if (dialog?.kind === "confirm") dialog.run();
    await settle();
    expect(fake.called("quit_confirmed")).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run them: FAIL**

- [ ] **Step 3: Implement in `app.ts`**

```ts
const ACTION_METHODS = {
  start: "plot_start",
  continue: "plot_continue",
  pause: "plot_pause",
  resume: "plot_resume",
  home: "plot_home",
  cancel: "plot_cancel",
  reconnect: "plot_reconnect",
  rehomed: "plot_rehomed",
  retry: "plot_retry",
} as const;
export type PlotAction = keyof typeof ACTION_METHODS;
const STOP_WAIT_MS = 60_000;
```

Methods (a new "Plotting" section):

```ts
  // Plotting (spec §4.4).

  /** One of plot.actions. Pause never waits behind another plotter request; the rest take their turn. */
  async plotAction(action: PlotAction): Promise<boolean> {
    const method = ACTION_METHODS[action];
    try {
      const reply = action === "pause" ? await this.client.call(method) : await this.client.hardware(method);
      this.setMachine(reply.machine);
      if (reply.plot.state !== this.state.plot.state) this.onPlotState(reply.plot);
      return true;
    } catch (error) {
      this.fail(error);
      await this.refreshPlot();
      return false;
    }
  }

  async startPlot(): Promise<void> {
    if (this.blocked("start")) return;
    if (this.state.notice?.source === "plot") this.dismissNotice();
    await this.plotAction("start");
  }

  pause(): void {
    if (this.blocked("pause")) return;
    void this.plotAction("pause");
  }

  /** Stop: a trace stops at once; a plot asks first, then pauses and is cancelled (bridge.md). */
  stopPlot(): void {
    if (this.blocked("stop")) return;
    if (this.state.plot.state === "tracing") {
      void this.attempt(() => this.client.call("plotter_stop"));
      return;
    }
    this.store.update({
      dialog: {
        kind: "confirm",
        title: "Stop the plot?",
        message: "The pen lifts and this plot can't be resumed.",
        confirm: "Stop",
        cancel: "Keep plotting",
        run: () => void this.pauseThenCancel(),
      },
    });
  }

  private async pauseThenCancel(): Promise<void> {
    this.closeDialog();
    if (!(await this.plotAction("pause"))) return;
    try {
      const state = await this.waitForPlot(["paused", "paused_at_home", ...AT_REST], STOP_WAIT_MS);
      if (state === "paused" || state === "paused_at_home") await this.plotAction("cancel");
    } catch (error) {
      this.fail(error);
    }
  }

  /** Resolves with the plot's state once it's one of `states`; fails after `ms`. */
  waitForPlot(states: string[], ms: number): Promise<string> {
    return new Promise((resolve, reject) => {
      let unsubscribe = () => {};
      const timer = setTimeout(() => {
        unsubscribe();
        reject(new BridgeError("The plot didn't stop in time. Click Pause, then Cancel plot."));
      }, ms);
      const check = () => {
        if (!states.includes(this.state.plot.state)) return;
        clearTimeout(timer);
        unsubscribe();
        resolve(this.state.plot.state);
      };
      unsubscribe = this.store.subscribe(check);
      check();
    });
  }

  async trace(): Promise<void> {
    if (this.blocked("trace")) return;
    await this.plotterAction(() => this.client.hardware("plot_trace"));
  }

  /** The window was closed mid-plot (close_requested): ask, then pause and close (spec §4.4). */
  private askToClose(): void {
    this.store.update({
      dialog: {
        kind: "confirm",
        title: "Stop the plot and close Rosetta Plotter?",
        message: "The pen lifts where it is.",
        confirm: "Stop and close",
        cancel: "Keep plotting",
        run: () => {
          this.closeDialog();
          void this.exit();
        },
      },
    });
  }
```

Replace the empty `showPlotNotice` with:

```ts
  /** The strip for plot states that need the student (spec §4.4), and the result when a plot ends. */
  private showPlotNotice(plot: PlotStatus, before: string): void {
    const run = (action: PlotAction) => () => void this.plotAction(action);
    const cancel = { label: "Cancel plot", run: run("cancel") };
    const needs: Record<string, Notice> = {
      reconnect: { kind: "warning", message: plot.message, details: plot.details, actions: [{ label: "Continue", run: run("reconnect") }, cancel] },
      slide_home: { kind: "warning", message: plot.message, actions: [{ label: "It's in the corner", run: run("rehomed") }, cancel] },
      not_connected: { kind: "error", message: plot.message, details: plot.details, actions: [{ label: "Retry", run: run("retry") }, cancel] },
    };
    const notice = needs[plot.state];
    if (notice) {
      this.notify({ ...notice, source: "plot" });
      return;
    }
    if (this.state.notice?.source === "plot") this.dismissNotice();
    if (plot.state === before) return;
    if (plot.state === "done") {
      this.notify({
        kind: "info",
        source: "plot",
        message: plot.message || "Done! The pen is back Home.",
        actions: [{ label: "Plot another copy", run: () => void this.startPlot() }],
      });
    } else if (AT_REST.includes(plot.state) && !AT_REST.includes(before) && plot.message) {
      this.notify({ kind: plot.details ? "error" : "info", source: "plot", message: plot.message, details: plot.details || undefined });
    }
  }
```

Remove the stub `askToClose` added in Task 7.

- [ ] **Step 4: Run: PASS**

Run: `npx vitest run src/app/plot.test.ts` (3×), `npm test`, `npm run typecheck`

- [ ] **Step 5: Commit**

```bash
git add ui/src/app
git commit -m "feat(ui): Start, Pause, Stop (ask, pause, cancel), pen changes, recovery in the strip, Plot another copy, close mid-plot"
```

---

## Task 9: The plot controls in the control bar

**Why:** Spec §2.2, right end:
- colored chips with each pen's time, then the total (time left while plotting);
- Start / Pause / Stop, or Resume / Return Home / Cancel plot while paused;
- greyed buttons with "Pausing…" or "Sending the pen Home…";
- a thin progress line along the bar's bottom;
- the paper fields locked during a plot;
- the status bar saying "Keep the laptop open while plotting."

**Files:**
- Create: `ui/src/ui/plotbar.ts`, `ui/src/ui/plotbar.test.ts`
- Modify: `ui/src/ui/controlbar.ts`, `ui/src/ui/statusbar.ts`, `ui/src/ui/icons.ts`

- [ ] **Step 1: Icons**

Add to `icons.ts`:
- imports: `play` from `@tabler/icons/outline/player-play.svg?raw`, `pause` from `…/player-pause.svg?raw`, `stop` from `…/player-stop.svg?raw`, `route` from `…/route.svg?raw`, `trace` from `…/border-outer.svg?raw`, `settings` from `…/settings.svg?raw`;
- each of the six names in the `ICONS` object.

- [ ] **Step 2: Write the failing tests**

Create `ui/src/ui/plotbar.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import "./plotbar";
import "./controlbar";
import { mount, readyToPlot, settle, shadow } from "../test/setup";

type Lit = HTMLElement & { updateComplete: Promise<unknown> };

function button(root: ShadowRoot, label: string): HTMLButtonElement {
  const found = Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === label);
  if (!found) throw new Error(`no button ${label}`);
  return found as HTMLButtonElement;
}

describe("plot bar", () => {
  it("shows each pen's time and the total, and Start is ready", async () => {
    const { app } = await readyToPlot();
    const bar = await mount<Lit>("rp-plotbar");
    const root = shadow(bar);
    expect(root.querySelectorAll(".chip")).toHaveLength(2);
    expect(root.querySelector(".total")?.textContent).toMatch(/^Total \d+:\d\d$/);
    expect(button(root, "Start").getAttribute("aria-disabled")).toBe("false");
    expect(button(root, "Pause").getAttribute("aria-disabled")).toBe("true");
    button(root, "Start").click();
    await settle();
    expect(app.state.plot.state).toBe("load_pen");
  });

  it("says why Start is greyed out when clicked", async () => {
    const { app } = await readyToPlot();
    app.store.update({ summary: null, preparing: true });
    const root = shadow(await mount<Lit>("rp-plotbar"));
    expect(root.querySelector(".total")?.textContent).toBe("…");
    button(root, "Start").click();
    expect(app.state.notice?.message).toBe("The plot is being prepared.");
  });

  it("while paused offers Resume, Return Home and Cancel plot", async () => {
    const { app } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    await app.plotAction("pause");
    await settle();
    const bar = await mount<Lit>("rp-plotbar");
    const labels = Array.from(shadow(bar).querySelectorAll("button")).map((b) => b.textContent?.trim());
    expect(labels).toEqual(["Resume", "Return Home", "Cancel plot"]);
  });

  it("shows time left while plotting", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    fake.progress(0.5);
    const bar = await mount<Lit>("rp-plotbar");
    expect(shadow(bar).querySelector(".total")?.textContent).toMatch(/left$/);
  });
});
```

`readyToPlot` comes from `ui/src/test/setup.ts` (Task 7).

- [ ] **Step 3: Run: FAIL** (`rp-plotbar` doesn't exist)

- [ ] **Step 4: Implement `ui/src/ui/plotbar.ts`**

```ts
/** The control bar's right end (spec §2.2): pen times and the total, and the plot buttons. */
import { css, html, nothing } from "lit";
import { StoreController } from "../state/store";
import { disabledReason } from "../state/reasons";
import { formatDuration } from "../state/plotting";
import { AppElement } from "./base";
import { icon, type IconName } from "./icons";
import { controls } from "./styles";

interface PlotButton {
  label: string;
  iconName?: IconName;
  primary?: boolean;
  reason: string | null;
  run: () => void;
}

const WAITING: Record<string, string> = { pausing: "Pausing…", homing: "Sending the pen Home…" };

function swatch(color: string): string {
  return color === "#000000" ? "var(--ink-black)" : color;
}

export class RpPlotbar extends AppElement {
  static styles = [
    controls,
    css`
      :host {
        display: flex;
        align-items: center;
        gap: 6px;
        white-space: nowrap;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: var(--text-dim);
      }
      .chip i {
        width: 9px;
        height: 9px;
        border-radius: 2px;
      }
      .total {
        margin: 0 6px 0 2px;
        color: var(--text);
      }
      .waiting {
        color: var(--text-dim);
      }
    `,
  ];

  constructor() {
    super();
    new StoreController(this, this.app.progress);
  }

  private buttons(): PlotButton[] {
    const { app, s } = this;
    const state = s.plot.state;
    if (state === "paused" || state === "paused_at_home") {
      return [
        { label: "Resume", iconName: "play", primary: true, reason: null, run: () => void app.plotAction("resume") },
        ...(state === "paused" ? [{ label: "Return Home", iconName: "home" as IconName, reason: null, run: () => void app.plotAction("home") }] : []),
        { label: "Cancel plot", reason: null, run: () => void app.plotAction("cancel") },
      ];
    }
    const waiting = WAITING[state];
    return [
      { label: "Start", iconName: "play", primary: true, reason: waiting ?? disabledReason("start", s), run: () => void app.startPlot() },
      { label: "Pause", iconName: "pause", reason: waiting ?? disabledReason("pause", s), run: () => app.pause() },
      { label: "Stop", iconName: "stop", reason: waiting ?? disabledReason("stop", s), run: () => app.stopPlot() },
    ];
  }

  private times() {
    const s = this.s;
    const progress = this.app.progress.state.value;
    if (s.preparing) return html`<span class="total" title="The plot is being prepared.">…</span>`;
    if (!s.summary) {
      const why = s.prepareProblem ?? (s.machine.model === null ? "Times appear once the plotter's model is known." : "Times appear once something is placed.");
      return html`<span class="total" title=${why}>—</span>`;
    }
    const chips = s.summary.layers.map(
      (layer) => html`<span class="chip" title=${`${layer.name} pen`}><i style=${`background: ${swatch(layer.color)}`}></i>${formatDuration(layer.seconds)}</span>`,
    );
    const warnings = s.summary.warnings.join(" ");
    const total = progress && !["idle", "ready", "done"].includes(s.plot.state)
      ? `${formatDuration(progress.seconds_left)} left`
      : `Total ${formatDuration(s.summary.total_seconds)}`;
    return html`${chips}<span class="total" title=${warnings}>${total}</span>${warnings ? html`<span class="chip" title=${warnings}>${icon("alert")}</span>` : nothing}`;
  }

  render() {
    const waiting = WAITING[this.s.plot.state];
    return html`${this.times()}${waiting ? html`<span class="waiting">${waiting}</span>` : nothing}${this.buttons().map(
      (b) => html`<button
        class=${b.primary ? "primary" : ""}
        aria-disabled=${b.reason ? "true" : "false"}
        title=${b.reason ?? b.label}
        @click=${() => (b.reason ? this.app.explain(b.reason) : b.run())}
      >
        ${b.iconName ? icon(b.iconName) : nothing}${b.label}
      </button>`,
    )}`;
  }
}

customElements.define("rp-plotbar", RpPlotbar);
```

If `styles.ts`'s `controls` has no `button.primary` rule (the accent fill), add one there:

```css
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.primary[aria-disabled="true"] { background: var(--panel-raised); border-color: var(--line); color: var(--text-faint); }
```

- [ ] **Step 5: Put it in the control bar, with the progress line and the paper lock (`controlbar.ts`)**

- Import `"./plotbar"`, `StoreController`, `overallFraction`, `plotRunning`.
- Add `new StoreController(this, this.app.progress);` in a constructor (after `super()`).
- Give `:host` the rule `position: relative;`, and add:

```css
      .spacer { flex: 1; }
      .progress {
        position: absolute;
        left: 0;
        bottom: 0;
        height: 2px;
        background: var(--accent);
      }
```

- `render()` becomes:

```ts
  render() {
    const s = this.s;
    const left = s.selection.length > 0 ? this.drawingControls() : this.paperControls();
    const fraction = plotRunning(s) && s.summary ? overallFraction(s.summary.total_seconds, this.app.progress.state.value) : 0;
    return html`${left}<span class="spacer"></span><rp-plotbar></rp-plotbar>${fraction > 0
        ? html`<div class="progress" style=${`width: ${(fraction * 100).toFixed(1)}%`}></div>`
        : nothing}`;
  }
```

- In `paperControls()`, compute `const locked = disabledReason("paper", s);`. Then:
  - the paper select and the orientation buttons get `?disabled=${!!locked}` and `title=${locked ?? ""}`;
  - the W/H/X/Y/Margin fields get `?disabled=${!!locked}`, with `tip=${locked ?? …existing tip}`.

  Plain `disabled` is acceptable on fields, as in Plan 2b-1's drawing fields.

- [ ] **Step 6: Status bar while plotting (`statusbar.ts`)**

- Add `new StoreController(this, this.app.progress);` beside the cursor controller.
- The pen position while plotting comes from the progress event: `const live = this.app.progress.state.value; const pen = plotRunning(this.s) && live ? ([live.x, live.y] as Point) : m.position;`. Use `where(pen)`.
- Before the spacer, add `${plotRunning(this.s) ? html`<span class="bad">Keep the laptop open while plotting.</span>` : nothing}`.

- [ ] **Step 7: Run: PASS**

Run: `npx vitest run src/ui/plotbar.test.ts` (3×), `npm test`, `npm run typecheck`

- [ ] **Step 8: Commit**

```bash
git add ui/src
git commit -m "feat(ui): pen times, total and time left, Start/Pause/Stop and Resume/Return Home/Cancel plot in the control bar"
```

---

## Task 10: The pen-change dialog and confirmations

**Why:** Spec §4.4.
- `load_pen` shows a modal: the color swatch, Python's message ("Put the red pen in the holder (2 of 3), then click Continue."), and the buttons Continue and Cancel plot.
- The Stop and close-mid-plot questions (Task 8's `confirm` dialogs) need drawing.

**Files:**
- Modify: `ui/src/ui/dialogs.ts`, `ui/src/shortcuts.ts`
- Test: `ui/src/ui/dialogs.test.ts`

- [ ] **Step 1: Write the failing tests**

Add to `ui/src/ui/dialogs.test.ts` (import `readyToPlot` from `../test/setup`):

```ts
describe("plot dialogs", () => {
  it("asks for the next pen, and Continue plots it", async () => {
    const { app } = await readyToPlot();
    const dialogs = await mount<Lit>("rp-dialogs");
    await app.startPlot();
    await dialogs.updateComplete;
    const root = shadow(dialogs);
    expect(root.querySelector("h2")?.textContent).toBe("Change the pen");
    expect(root.querySelector(".message")?.textContent).toBe("Put the black pen in the holder (1 of 2), then click Continue.");
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await settle();
    expect(app.state.plot.state).toBe("plotting");
  });

  it("Esc doesn't cancel the plot from the pen-change dialog", async () => {
    const { app } = await readyToPlot();
    await mount<Lit>("rp-dialogs");
    await app.startPlot();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    await settle();
    expect(app.state.plot.state).toBe("load_pen");
  });

  it("draws a confirmation with its two buttons", async () => {
    const { app } = await startApp();
    const dialogs = await mount<Lit>("rp-dialogs");
    let ran = false;
    app.store.update({ dialog: { kind: "confirm", title: "Stop the plot?", message: "The pen lifts.", confirm: "Stop", cancel: "Keep plotting", run: () => (ran = true) } });
    await dialogs.updateComplete;
    const labels = Array.from(shadow(dialogs).querySelectorAll("button")).map((b) => b.textContent?.trim());
    expect(labels).toEqual(["Keep plotting", "Stop"]);
    (shadow(dialogs).querySelector("button.primary") as HTMLButtonElement).click();
    expect(ran).toBe(true);
  });
});
```

Add to the "shortcuts while a dialog is open" block: `handleShortcut` returns `false` for Delete while `app.state.plot.state === "load_pen"`.

- [ ] **Step 2: Run: FAIL**

- [ ] **Step 3: Implement (`dialogs.ts`)**

- `render()` shows the pen dialog whenever the plot asks for a pen, ahead of any other dialog:

```ts
  render() {
    const s = this.s;
    if (s.plot.state === "load_pen") return this.frame(this.penChange());
    const dialog = s.dialog;
    if (!dialog) return nothing;
    return this.frame(this.body(dialog), () => this.cancel());
  }

  private frame(body: unknown, onBackdrop?: () => void) {
    return html`<div class="backdrop" @click=${(e: Event) => e.target === e.currentTarget && onBackdrop?.()}>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="title">${body}</div>
    </div>`;
  }

  private penChange() {
    const plot = this.s.plot;
    const color = plot.color === "#000000" ? "var(--ink-black)" : (plot.color ?? "transparent");
    return html`<h2 id="title">Change the pen</h2>
      <div class="pen"><i style=${`background: ${color}`}></i><p class="message">${plot.message}</p></div>
      <div class="buttons">
        <button @click=${() => void this.app.plotAction("cancel")}>Cancel plot</button>
        <button class="primary" @click=${() => void this.app.plotAction("continue")}>Continue</button>
      </div>`;
  }
```

- Add the `confirm` case to `body()`:

```ts
      case "confirm":
        return html`<h2 id="title">${dialog.title}</h2>
          ${dialog.message ? html`<p class="message">${dialog.message}</p>` : nothing}
          <div class="buttons">
            <button @click=${() => this.app.closeDialog()}>${dialog.cancel}</button>
            <button class="primary" @click=${() => dialog.run()}>${dialog.confirm}</button>
          </div>`;
```

- Add these styles:

```css
      .pen { display: flex; gap: 12px; align-items: center; }
      .pen i { flex: none; width: 28px; height: 28px; border-radius: 4px; border: 1px solid var(--line); }
```

- `onKey`: the pen dialog counts as open, but Esc doesn't cancel it. Change its first line to `if (!this.s.dialog && this.s.plot.state !== "load_pen") return;`. In the Escape branch, only call `this.cancel()` when `this.s.dialog` is set; with only the pen dialog open, Esc does nothing.
- `updated()` focus: treat the pen dialog as a dialog too. Compare `this.s.plot.state === "load_pen" ? "pen" : this.s.dialog` against `lastDialog`.

In `shortcuts.ts`, replace the `app.state.dialog` check added in Task 3 with `if (modalOpen(app.state)) return false;` (import `modalOpen` from `./state/selectors`).

- [ ] **Step 4: Run: PASS**

Run: `npx vitest run src/ui/dialogs.test.ts` (3×), `npm test`, `npm run typecheck`

- [ ] **Step 5: Commit**

```bash
git add ui/src
git commit -m "feat(ui): the pen-change dialog and plot confirmations"
```


---

## Task 11: The plate during a plot: crosshair and lines already drawn

**Why:** Spec §4.4 `plotting`:
- the crosshair follows `plot_progress`;
- lines already drawn darken.

The route math (one timeline across pens) is shared with Preview path (Task 12).

**Files:**
- Create: `ui/src/geometry/route.ts`, `ui/src/geometry/route.test.ts`
- Modify: `ui/src/ui/plate.ts`
- Test: `ui/src/ui/plate.test.ts`

- [ ] **Step 1: Write the failing route tests**

Create `ui/src/geometry/route.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { PlotSummary } from "../bridge/contract";
import { pointAt, routeOf, routePath } from "./route";

const summary: PlotSummary = {
  layers: [
    {
      layer: 1, color: "#000000", name: "black", seconds: 2, pendown_mm: 10,
      path: [
        { down: false, points: [0, 0, 0, 10, 0, 1] },
        { down: true, points: [10, 0, 1, 10, 10, 2] },
      ],
    },
    { layer: 2, color: "#ff0000", name: "red", seconds: 2, pendown_mm: 5, path: [{ down: true, points: [0, 0, 0, 0, 5, 1] }] },
  ],
  total_seconds: 4,
  ink_bbox: [0, 0, 10, 10],
  warnings: [],
};

describe("route", () => {
  it("puts the pens one after another on one timeline", () => {
    const route = routeOf(summary);
    expect(route.total).toBe(4);
    expect(route.layerStarts).toEqual([0, 2]);
    expect(routeOf(summary)).toBe(route); // cached
  });

  it("finds the pen at a time", () => {
    const route = routeOf(summary);
    expect(pointAt(route, 0)).toEqual([0, 0]);
    expect(pointAt(route, 1.5)).toEqual([10, 5]);
    expect(pointAt(route, 2.5)).toEqual([0, 2.5]);
    expect(pointAt(route, 99)).toEqual([0, 5]);
  });

  it("draws one pen's moves, all of them or up to a time", () => {
    const route = routeOf(summary);
    expect(routePath(route, 0, true)).toBe("M10 0L10 10");
    expect(routePath(route, 0, true, 1.5)).toBe("M10 0L10 5");
    expect(routePath(route, 0, false)).toBe("M0 0L10 0");
    expect(routePath(route, 1, true, 2)).toBe("");
  });
});
```

Run: `npx vitest run src/geometry/route.test.ts`. Expected: FAIL (no module).

- [ ] **Step 2: Implement `ui/src/geometry/route.ts`**

```ts
/**
 * The prepared plot's planned route (bridge.md summary.path) as one timeline: pen after pen, times in
 * seconds from the start of the whole plot, points in machine mm from Home. Used to show the lines
 * already drawn during a plot, and by Preview path.
 */
import type { PlotSummary } from "../bridge/contract";
import type { Point } from "./placement";

export interface Segment {
  layer: number;
  down: boolean;
  x0: number;
  y0: number;
  t0: number;
  x1: number;
  y1: number;
  t1: number;
}

export interface Route {
  segments: Segment[];
  total: number;
  /** When each pen starts, in seconds from the start of the plot. */
  layerStarts: number[];
}

const cache = new WeakMap<PlotSummary, Route>();

export function routeOf(summary: PlotSummary): Route {
  const known = cache.get(summary);
  if (known) return known;
  const segments: Segment[] = [];
  const layerStarts: number[] = [];
  let offset = 0;
  summary.layers.forEach((layer, index) => {
    layerStarts.push(offset);
    let end = 0;
    for (const run of layer.path) {
      const p = run.points;
      for (let i = 0; i + 5 < p.length; i += 3) {
        segments.push({ layer: index, down: run.down, x0: p[i], y0: p[i + 1], t0: offset + p[i + 2], x1: p[i + 3], y1: p[i + 4], t1: offset + p[i + 5] });
        end = Math.max(end, p[i + 5]);
      }
    }
    offset += Math.max(layer.seconds, end);
  });
  const route = { segments, total: offset, layerStarts };
  cache.set(summary, route);
  return route;
}

function along(seg: Segment, t: number): Point {
  if (t >= seg.t1) return [seg.x1, seg.y1];
  const k = seg.t1 > seg.t0 ? (t - seg.t0) / (seg.t1 - seg.t0) : 1;
  return [seg.x0 + (seg.x1 - seg.x0) * k, seg.y0 + (seg.y1 - seg.y0) * k];
}

/** Where the pen is at time t. */
export function pointAt(route: Route, t: number): Point | null {
  const s = route.segments;
  if (s.length === 0) return null;
  if (t <= s[0].t0) return [s[0].x0, s[0].y0];
  let lo = 0;
  let hi = s.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (s[mid].t1 < t) lo = mid + 1;
    else hi = mid;
  }
  return along(s[lo], t);
}

/** An SVG path of one pen's pen-down (or pen-up) moves, up to time `until`. */
export function routePath(route: Route, layer: number, down: boolean, until = Infinity): string {
  const parts: string[] = [];
  let last: Point | null = null;
  for (const seg of route.segments) {
    if (seg.layer !== layer || seg.down !== down || seg.t0 >= until) continue;
    const end = along(seg, until);
    if (!last || last[0] !== seg.x0 || last[1] !== seg.y0) parts.push(`M${seg.x0} ${seg.y0}`);
    parts.push(`L${end[0]} ${end[1]}`);
    last = end;
  }
  return parts.join("");
}
```

Run the route tests: PASS.

- [ ] **Step 2b: Check that Python's path really is in machine mm from Home**

Read `src/rosetta/engine/preview.py` (`_Recorder`) and `plotjob._plan_job`. The path should come from the plot SVG, whose page is the plotter's reach with (0, 0) at Home, so it's in the same frame as `plot_progress`'s x and y.
- If it is (expected), add one sentence to `docs/bridge.md` under **summary**: "`path` points and `plot_progress` x, y are machine mm from Home, the same frame as `material`."
- If it isn't, stop and report the frame instead of guessing.

- [ ] **Step 3: Write the failing plate test**

Add to `ui/src/ui/plate.test.ts` (import `readyToPlot` from `../test/setup`):

```ts
  it("while plotting, follows the pen and darkens what's drawn", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    fake.progress(0.5);
    const plate = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-plate");
    await plate.updateComplete;
    const root = shadow(plate);
    expect(root.querySelector("path.drawn")?.getAttribute("d")).toMatch(/^M/);
    expect(root.querySelector("rect.cross-box")).not.toBeNull();
  });
```

- [ ] **Step 4: Implement (`plate.ts`)**

- Imports: `StoreController` (from `../state/store`), and `routeOf`, `routePath`, `pointAt` (from `../geometry/route`; `pointAt` is used in Task 12).
- In the constructor, after `super()`, add `new StoreController(this, this.app.progress);`. If `RpPlate` has no constructor, add one.
- Add this method and call it in `render()` inside the machine-units `<g>`, after the clipped ink group: `${this.drawnSoFar()}`.

```ts
  /** While plotting: the lines already drawn, darker (spec §4.4). */
  private drawnSoFar() {
    const s = this.s;
    const progress = this.app.progress.state.value;
    if (!s.summary || !progress || !plotRunning(s)) return nothing;
    const route = routeOf(s.summary);
    const current = s.summary.layers[progress.layer];
    if (!current) return nothing;
    const until = route.layerStarts[progress.layer] + current.seconds * progress.fraction;
    return s.summary.layers.slice(0, progress.layer + 1).map(
      (layer, index) =>
        svg`<path class="drawn" d=${routePath(route, index, true, index < progress.layer ? Infinity : until)} style=${`stroke: ${inkColor(layer.color)}`} />`,
    );
  }
```

- The crosshair shows the live position while plotting. In `crosshair()`:

```ts
    const live = this.app.progress.state.value;
    const position = plotRunning(this.s) && live ? ([live.x, live.y] as Point) : this.s.machine.position;
```

- Add this style:

```css
      .drawn {
        fill: none;
        stroke-width: 2.5px;
        vector-effect: non-scaling-stroke;
        stroke-linecap: round;
        stroke-linejoin: round;
      }
```

- [ ] **Step 5: Run: PASS**

Run: `npm test`, `npm run typecheck`

- [ ] **Step 6: Commit**

```bash
git add ui/src docs/bridge.md
git commit -m "feat(ui): the plate follows the pen and darkens lines already drawn during a plot"
```

---

## Task 12: Preview path

**Why:** Spec §4.5.
- Preview path draws the planned route: pen-down moves in their pen color, pen-up moves as faint dashes.
- An animated dot follows the route.
- The control bar shows a scrubber with play/pause and 1× / 4× / 16× speed.
- Esc or another tool ends it.

**Files:**
- Modify: `ui/src/app/app.ts`, `ui/src/ui/plate.ts`, `ui/src/ui/controlbar.ts`, `ui/src/shortcuts.ts`
- Test: `ui/src/app/plot.test.ts`, `ui/src/ui/plate.test.ts`, `ui/src/ui/controlbar.test.ts`

- [ ] **Step 1: Write the failing tests**

Add to `ui/src/app/plot.test.ts`:

```ts
describe("preview path", () => {
  it("plays at the chosen speed and stops at the end", async () => {
    const { app } = await readyToPlot();
    app.startPreview();
    expect(app.state.preview).toEqual({ playing: true, speed: 1 });
    app.tickPreview(1000);
    expect(app.previewClock.state.t).toBeCloseTo(1);
    app.setPreviewSpeed(16);
    app.tickPreview(1000);
    expect(app.previewClock.state.t).toBeCloseTo(17);
    app.tickPreview(10_000_000);
    expect(app.state.preview?.playing).toBe(false);
    app.endPreview();
  });

  it("explains when the times aren't ready, and ends with another tool", async () => {
    const { app } = await startApp();
    app.startPreview();
    expect(app.state.preview).toBeNull();
    expect(app.state.notice?.message).toBe("Nothing placed on the paper.");
    const ready = await readyToPlot();
    ready.app.startPreview();
    ready.app.setTool("hand");
    expect(ready.app.state.preview).toBeNull();
  });
});
```

Add to `ui/src/ui/plate.test.ts`:

```ts
  it("Preview path draws the route and a dot", async () => {
    const { app } = await readyToPlot();
    app.startPreview();
    app.tickPreview(500);
    const plate = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-plate");
    await plate.updateComplete;
    const root = shadow(plate);
    expect(root.querySelectorAll("path.route-down").length).toBe(2);
    expect(root.querySelector("circle.route-dot")).not.toBeNull();
    app.endPreview();
  });
```

Add to `ui/src/ui/controlbar.test.ts`:

```ts
describe("control bar, preview path", () => {
  it("has a scrubber and speeds", async () => {
    const { app } = await readyToPlot();
    app.startPreview();
    app.playPreview(false);
    const root = shadow(await mount("rp-controlbar"));
    const scrubber = root.querySelector('input[type="range"]') as HTMLInputElement;
    scrubber.value = "3";
    scrubber.dispatchEvent(new Event("input"));
    expect(app.previewClock.state.t).toBe(3);
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === "4×") as HTMLButtonElement).click();
    expect(app.state.preview?.speed).toBe(4);
    app.endPreview();
  });
});
```

- [ ] **Step 2: Run: FAIL**

- [ ] **Step 3: Implement the clock in `app.ts`**

Import `routeOf` from `../geometry/route`, then add:

```ts
const PREVIEW_TICK_MS = 33;
```

```ts
  /** Preview path's clock (seconds from the start of the plot): its own store, as it ticks 30 times a second. */
  readonly previewClock = new Store<{ t: number }>({ t: 0 });
  private previewTimer: ReturnType<typeof setInterval> | null = null;
```

```ts
  // Preview path (spec §4.5).

  startPreview(): void {
    if (this.blocked("preview")) return;
    this.previewClock.update({ t: 0 });
    this.store.update({ preview: { playing: true, speed: 1 } });
    if (!this.previewTimer) this.previewTimer = setInterval(() => this.tickPreview(PREVIEW_TICK_MS), PREVIEW_TICK_MS);
  }

  endPreview(): void {
    if (this.previewTimer) clearInterval(this.previewTimer);
    this.previewTimer = null;
    if (this.state.preview) this.store.update({ preview: null });
  }

  playPreview(playing: boolean): void {
    const preview = this.state.preview;
    if (!preview || !this.state.summary) return;
    if (playing && this.previewClock.state.t >= routeOf(this.state.summary).total) this.previewClock.update({ t: 0 });
    this.store.update({ preview: { ...preview, playing } });
  }

  setPreviewSpeed(speed: 1 | 4 | 16): void {
    const preview = this.state.preview;
    if (preview) this.store.update({ preview: { ...preview, speed } });
  }

  seekPreview(t: number): void {
    const total = this.state.summary ? routeOf(this.state.summary).total : 0;
    this.previewClock.update({ t: Math.min(total, Math.max(0, t)) });
  }

  /** Move the preview on by `ms` of real time (its timer calls this; tests call it directly). */
  tickPreview(ms: number): void {
    const { preview, summary } = this.state;
    if (!preview?.playing || !summary) return;
    const total = routeOf(summary).total;
    const t = Math.min(total, this.previewClock.state.t + (ms / 1000) * preview.speed);
    this.previewClock.update({ t });
    if (t >= total) this.store.update({ preview: { ...preview, playing: false } });
  }
```

- `setTool` starts with `if (this.state.preview) this.endPreview();`.
- In `onPlotState`, when `plot.state === "idle"`, also call `this.endPreview()`, since the plot changed and the route is gone.
- `stop()` (the App's shutdown, not the plot's Stop) also clears `previewTimer`.

In `shortcuts.ts`, the Escape branch becomes:

```ts
  if (event.key === "Escape") {
    if (app.state.preview) app.endPreview();
    else if (app.state.homing) app.cancelHoming();
    else if (!modalOpen(app.state)) app.deselect();
    return false;
  }
```

- [ ] **Step 4: Draw it (`plate.ts`)**

- Add `new StoreController(this, this.app.previewClock);` in the constructor.
- Cache the route's path strings per summary, since the dot moves 30 times a second but the paths don't change:

```ts
  private readonly routePaths = new WeakMap<object, { up: string[]; down: string[] }>();

  private previewRoute() {
    const s = this.s;
    if (!s.preview || !s.summary) return nothing;
    let paths = this.routePaths.get(s.summary);
    if (!paths) {
      const route = routeOf(s.summary);
      paths = {
        up: s.summary.layers.map((_, i) => routePath(route, i, false)),
        down: s.summary.layers.map((_, i) => routePath(route, i, true)),
      };
      this.routePaths.set(s.summary, paths);
    }
    const p = paths;
    return s.summary.layers.map(
      (layer, i) => svg`<path class="route-up" d=${p.up[i]} /><path class="route-down" d=${p.down[i]} style=${`stroke: ${inkColor(layer.color)}`} />`,
    );
  }

  private previewDot() {
    const s = this.s;
    if (!s.preview || !s.summary) return nothing;
    const at = pointAt(routeOf(s.summary), this.app.previewClock.state.t);
    if (!at) return nothing;
    const [cx, cy] = toScreen(this.camera, at);
    return svg`<circle class="route-dot" cx=${cx} cy=${cy} r="4" />`;
  }
```

- In `render()`:
  - add `${this.previewRoute()}` inside the machine-units group after `drawnSoFar()`;
  - add `${this.previewDot()}` beside `${this.crosshair()}`;
  - give the `<svg>` `class=${s.preview ? "previewing" : ""}`.
- Add these styles:

```css
      svg.previewing .ink { opacity: 0.25; }
      .route-down { fill: none; stroke-width: 1.5px; vector-effect: non-scaling-stroke; }
      .route-up { fill: none; stroke: var(--text-faint); stroke-width: 1px; stroke-dasharray: 3 3; vector-effect: non-scaling-stroke; }
      .route-dot { fill: var(--pen-cross); stroke: #fff; stroke-width: 1px; }
```

- [ ] **Step 5: The scrubber (`controlbar.ts`)**

- Add `new StoreController(this, this.app.previewClock);` in the constructor.
- Import `routeOf` and `formatDuration`.
- `render()`'s left part becomes `const left = s.preview ? this.previewControls() : s.selection.length > 0 ? this.drawingControls() : this.paperControls();`.

```ts
  private previewControls() {
    const s = this.s;
    const preview = s.preview;
    if (!preview) return nothing;
    const total = s.summary ? routeOf(s.summary).total : 0;
    const t = this.app.previewClock.state.t;
    return html`<span class="name">Preview path</span>
      <button class="icon" aria-label=${preview.playing ? "Pause the preview" : "Play the preview"} @click=${() => this.app.playPreview(!preview.playing)}>
        ${icon(preview.playing ? "pause" : "play")}
      </button>
      <input type="range" aria-label="Preview position" min="0" max=${total} step="0.1" .value=${String(t)}
        @input=${(e: Event) => this.app.seekPreview(Number((e.target as HTMLInputElement).value))} />
      <span>${formatDuration(t)} / ${formatDuration(total)}</span>
      ${([1, 4, 16] as const).map(
        (speed) => html`<button aria-pressed=${String(preview.speed === speed)} @click=${() => this.app.setPreviewSpeed(speed)}>${speed}×</button>`,
      )}
      <button class="icon" aria-label="Close the preview (Esc)" @click=${() => this.app.endPreview()}>${icon("x")}</button>`;
  }
```

- [ ] **Step 6: Run: PASS**

Run: `npm test` (the new tests 3×), `npm run typecheck`

- [ ] **Step 7: Commit**

```bash
git add ui/src
git commit -m "feat(ui): Preview path: the planned route, a moving dot, scrubber and 1×/4×/16×"
```

---

## Task 13: The Settings dialog

**Why:** Spec §4.7 (File › Settings):
- **General:** units, margin, grid, skip white shapes.
- **Advanced:** the engine options from `app_start().advanced_options`, checked in the page first. It sends only what changed (`set_advanced` merges). **Restore defaults** resets them all.

The snapping options wait for Plan 2b-3, when snapping exists.

**Files:**
- Create: `ui/src/state/advanced.ts`, `ui/src/state/advanced.test.ts`
- Modify: `ui/src/app/app.ts`, `ui/src/ui/dialogs.ts`
- Test: `ui/src/ui/dialogs.test.ts`

- [ ] **Step 1: Write the failing check tests**

Create `ui/src/state/advanced.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { FAKE_ADVANCED } from "../bridge/fake";
import { changedAdvanced, checkAdvanced } from "./advanced";

const options = {
  labels: { accel: "Acceleration", pen_up: "Pen-up height", reordering: "Path order", hiding: "Hidden-line removal" },
  ranges: { accel: [1, 100] as [number, number], pen_up: [0, 100] as [number, number] },
  choices: { reordering: [0, 1, 2, 4] },
  defaults: FAKE_ADVANCED,
};

describe("Advanced options", () => {
  it("are checked in the page, with Python's wording", () => {
    expect(checkAdvanced({ accel: 60, pen_up: null, hiding: true, reordering: 4 }, options)).toBeNull();
    expect(checkAdvanced({ accel: 500 }, options)).toBe("Acceleration must be from 1 to 100.");
    expect(checkAdvanced({ accel: 2.5 }, options)).toBe("Acceleration must be a whole number.");
    expect(checkAdvanced({ reordering: 3 }, options)).toBe("Path order must be one of 0, 1, 2, 4.");
  });

  it("send only what changed", () => {
    expect(changedAdvanced({ ...FAKE_ADVANCED, accel: 60 }, FAKE_ADVANCED)).toEqual({ accel: 60 });
  });
});
```

- [ ] **Step 2: Implement `ui/src/state/advanced.ts`**

```ts
/** The Advanced settings (spec §4.7): checked in the page first, with the same wording as Python. */
import type { AdvancedValues, AppStart } from "../bridge/contract";

type Options = AppStart["advanced_options"];

/** Options where null means "Rosetta decides" (shown as Automatic). */
export const AUTOMATIC = ["pen_up", "speed_pendown"];

/** A starting number when Automatic is turned off. */
export const MANUAL_START: Record<string, number> = { pen_up: 60, speed_pendown: 25 };

export const CHOICE_LABELS: Record<string, Record<number, string>> = {
  reordering: { 0: "Join nearby ends only", 1: "Reorder", 2: "Reorder and reverse", 4: "Keep the file's order" },
  resolution: { 1: "Fine", 2: "Coarse (faster)" },
};

export function checkAdvanced(values: AdvancedValues, options: Options): string | null {
  for (const [name, value] of Object.entries(values)) {
    const label = options.labels[name] ?? name;
    if (name === "hiding") continue;
    if (value === null && AUTOMATIC.includes(name)) continue;
    if (typeof value !== "number" || !Number.isInteger(value)) return `${label} must be a whole number.`;
    const choices = options.choices[name];
    if (choices && !choices.includes(value)) return `${label} must be one of ${choices.join(", ")}.`;
    const range = options.ranges[name];
    if (range && !(value >= range[0] && value <= range[1])) return `${label} must be from ${range[0]} to ${range[1]}.`;
  }
  return null;
}

export function changedAdvanced(draft: AdvancedValues, current: AdvancedValues): AdvancedValues {
  return Object.fromEntries(Object.entries(draft).filter(([name, value]) => value !== current[name]));
}
```

Run: `npx vitest run src/state/advanced.test.ts` → PASS.

- [ ] **Step 3: App actions (`app.ts`)**

```ts
  openSettings(): void {
    this.store.update({ dialog: { kind: "settings" } });
  }

  async setSkipWhite(skip: boolean): Promise<void> {
    this.store.update({ skipWhite: skip });
    const reply = await this.attempt(() => this.client.call("set_skip_white", skip));
    if (!reply) this.store.update({ skipWhite: !skip });
    this.refreshColors();
  }

  /** Send the Advanced options that changed. Returns Python's message if it refused them (shown in the dialog). */
  async setAdvanced(changes: AdvancedValues): Promise<string | null> {
    if (Object.keys(changes).length === 0) return null;
    try {
      const reply = await this.client.call("set_advanced", changes);
      this.store.update({ advanced: reply.advanced });
      this.schedulePrepare();
      return null;
    } catch (error) {
      return error instanceof BridgeError ? error.message : "Something unexpected went wrong.";
    }
  }
```

- [ ] **Step 4: Write the failing dialog tests**

Add to `ui/src/ui/dialogs.test.ts`:

```ts
describe("Settings", () => {
  async function openSettings() {
    const started = await startApp();
    const dialogs = await mount<Lit>("rp-dialogs");
    started.app.openSettings();
    await dialogs.updateComplete;
    return { ...started, dialogs, root: shadow(dialogs) };
  }

  function tab(root: ShadowRoot, name: string) {
    (Array.from(root.querySelectorAll('[role="tab"]')).find((b) => b.textContent?.trim() === name) as HTMLButtonElement).click();
  }

  it("General applies at once: skip white shapes", async () => {
    const { fake, root } = await openSettings();
    const skip = root.querySelector("#skip-white") as HTMLInputElement;
    skip.checked = false;
    skip.dispatchEvent(new Event("change"));
    await settle();
    expect(fake.called("set_skip_white")).toEqual([[false]]);
  });

  it("Advanced sends only what changed, after checking it", async () => {
    const { app, fake, dialogs, root } = await openSettings();
    tab(root, "Advanced");
    await dialogs.updateComplete;
    const accel = root.querySelector("#adv-accel") as HTMLInputElement;
    accel.value = "500";
    accel.dispatchEvent(new Event("change"));
    await dialogs.updateComplete;
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await dialogs.updateComplete;
    expect(root.querySelector(".hint")?.textContent).toBe("Acceleration must be from 1 to 100.");
    expect(fake.called("set_advanced")).toEqual([]);
    accel.value = "60";
    accel.dispatchEvent(new Event("change"));
    await dialogs.updateComplete;
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("set_advanced")).toEqual([[{ accel: 60 }]]);
    expect(app.state.advanced.accel).toBe(60);
    expect(app.state.dialog).toBeNull();
  });

  it("Restore defaults puts every option back", async () => {
    const { app, fake, dialogs, root } = await openSettings();
    await app.setAdvanced({ accel: 60, hiding: true });
    tab(root, "Advanced");
    await dialogs.updateComplete;
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Restore defaults") as HTMLButtonElement).click();
    await dialogs.updateComplete;
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("set_advanced").at(-1)).toEqual([{ accel: 75, hiding: false }]);
  });
});
```

- [ ] **Step 5: Run: FAIL**

- [ ] **Step 6: Implement the dialog (`dialogs.ts`)**

- Imports: `live` from `lit/directives/live.js`; `"./field"`; `AdvancedValues`; and `AUTOMATIC`, `CHOICE_LABELS`, `MANUAL_START`, `changedAdvanced`, `checkAdvanced` from `../state/advanced`; `UNITS`, `UNIT_NAMES` and `type Units` from `../geometry/units`.
- Add the properties `tab: { state: true }`, `draft: { state: true }` and `problem: { state: true }`, with these declarations and constructor defaults:

```ts
  declare tab: "general" | "advanced";
  declare draft: AdvancedValues;
  declare problem: string;
  // constructor: this.tab = "general"; this.draft = {}; this.problem = "";
```

- In `willUpdate`, when a `settings` dialog newly opens, set `this.tab = "general"; this.draft = { ...this.s.advanced }; this.problem = "";`.
- Add `case "settings": return this.settings();` to `body()`, plus these methods:

```ts
  private settings() {
    const s = this.s;
    const tabs = html`<div class="tabs" role="tablist">
      ${(["general", "advanced"] as const).map(
        (name) => html`<button role="tab" aria-selected=${String(this.tab === name)} @click=${() => (this.tab = name)}>
          ${name === "general" ? "General" : "Advanced"}
        </button>`,
      )}
    </div>`;
    if (this.tab === "general") {
      return html`<h2 id="title">Settings</h2>${tabs}
        <div class="form">
          <label for="units">Units</label>
          <select id="units" .value=${live(s.units)} @change=${(e: Event) => this.app.setUnits((e.target as HTMLSelectElement).value as Units)}>
            ${UNITS.map((u) => html`<option value=${u} ?selected=${u === s.units}>${UNIT_NAMES[u]}</option>`)}
          </select>
          <label>Margin</label>
          <rp-field label="" .value=${s.margin} .units=${s.units} tip="Margin" @commit=${(e: CustomEvent<number>) => this.app.setMargin(e.detail)}></rp-field>
          <label for="grid">Show grid</label>
          <input id="grid" type="checkbox" .checked=${s.view.grid} @change=${() => this.app.toggleView("grid")} />
          <label for="skip-white">Skip white shapes</label>
          <input id="skip-white" type="checkbox" .checked=${s.skipWhite}
            @change=${(e: Event) => void this.app.setSkipWhite((e.target as HTMLInputElement).checked)} />
        </div>
        <div class="buttons"><button class="primary" @click=${() => this.app.closeDialog()}>Close</button></div>`;
    }
    const options = s.start?.advanced_options;
    const names = options ? Object.keys(options.labels) : [];
    return html`<h2 id="title">Settings</h2>${tabs}
      <p class="dim">These change how the plotter moves. Most students never need them.</p>
      <div class="form">${names.map((name) => this.advancedRow(name))}</div>
      ${this.problem ? html`<p class="hint" role="alert">${this.problem}</p>` : nothing}
      <div class="buttons">
        <button @click=${() => options && ((this.draft = { ...options.defaults }), (this.problem = ""))}>Restore defaults</button>
        <span class="grow"></span>
        <button @click=${() => this.app.closeDialog()}>Cancel</button>
        <button class="primary" @click=${() => void this.saveAdvanced()}>Save</button>
      </div>`;
  }

  private advancedRow(name: string) {
    const options = this.s.start?.advanced_options;
    if (!options) return nothing;
    const label = options.labels[name];
    const value = this.draft[name];
    const id = `adv-${name}`;
    const set = (next: number | boolean | null) => {
      this.draft = { ...this.draft, [name]: next };
      this.problem = "";
    };
    if (name === "hiding") {
      return html`<label for=${id}>${label}</label>
        <input id=${id} type="checkbox" .checked=${value === true} @change=${(e: Event) => set((e.target as HTMLInputElement).checked)} />`;
    }
    const choices = options.choices[name];
    if (choices) {
      return html`<label for=${id}>${label}</label>
        <select id=${id} .value=${live(String(value))} @change=${(e: Event) => set(Number((e.target as HTMLSelectElement).value))}>
          ${choices.map((c) => html`<option value=${c} ?selected=${c === value}>${CHOICE_LABELS[name]?.[c] ?? c}</option>`)}
        </select>`;
    }
    const [low, high] = options.ranges[name] ?? [0, 100];
    const automatic = AUTOMATIC.includes(name);
    return html`<label for=${id}>${label}</label>
      <span class="inline">
        <input id=${id} type="number" min=${low} max=${high} step="1" ?disabled=${value === null}
          .value=${live(value === null || value === undefined ? "" : String(value))}
          @change=${(e: Event) => {
            const text = (e.target as HTMLInputElement).value.trim();
            set(text === "" ? Number.NaN : Number(text));
          }} />
        ${automatic
          ? html`<label><input type="checkbox" .checked=${value === null}
              @change=${(e: Event) => set((e.target as HTMLInputElement).checked ? null : (MANUAL_START[name] ?? low))} />Automatic</label>`
          : nothing}
      </span>`;
  }

  private async saveAdvanced(): Promise<void> {
    const options = this.s.start?.advanced_options;
    if (!options) return;
    const problem = checkAdvanced(this.draft, options);
    if (problem) {
      this.problem = problem;
      return;
    }
    const refused = await this.app.setAdvanced(changedAdvanced(this.draft, this.s.advanced));
    if (refused) this.problem = refused;
    else this.app.closeDialog();
  }
```

- Add these styles:

```css
      .tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); }
      .tabs [role="tab"] { border: none; background: none; border-bottom: 2px solid transparent; border-radius: 0; }
      .tabs [aria-selected="true"] { border-bottom-color: var(--accent); }
      .form { display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; align-items: center; }
      .inline { display: inline-flex; gap: 8px; align-items: center; }
      .grow { flex: 1; }
      .dim { color: var(--text-dim); }
```

- [ ] **Step 7: Run: PASS**

Run: `npx vitest run src/ui/dialogs.test.ts` (3×), `npm test`, `npm run typecheck`

- [ ] **Step 8: Commit**

```bash
git add ui/src
git commit -m "feat(ui): Settings dialog: General (units, margin, grid, skip white) and Advanced (checked, only changes sent, Restore defaults)"
```

---

## Task 14: Plot commands in the menus, tools and shortcuts; keep the window on the app's page

**Why:**
- Spec §2.1 to §2.3: Plotter › Trace outline · Preview path · Start (Ctrl+Enter) · Pause (Ctrl+Shift+P) · Stop; File › Settings… (Ctrl+,); the Trace and Preview tools.
- plan2-notes "Lock navigation": pywebview gives `js_api` to any page the window shows, so the window must never stay on a page other than the app's.

**Files:**
- Modify: `ui/src/ui/menubar.ts`, `ui/src/ui/tools.ts`, `ui/src/shortcuts.ts`, `ui/src/app/shortcut-help.ts`, `src/rosetta/app/main.py`
- Test: `ui/src/ui/menus.test.ts`, `tests/test_app_main.py`

- [ ] **Step 1: Write the failing tests**

Add to `ui/src/ui/menus.test.ts` (import `handleShortcut` from `../shortcuts`, and `readyToPlot`, `settle` from `../test/setup`):

```ts
describe("plot commands", () => {
  it("the Plotter menu has the plot commands, greyed with reasons", async () => {
    await startApp();
    const bar = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-menubar");
    (Array.from(shadow(bar).querySelectorAll("button.title")).find((b) => b.textContent?.trim() === "Plotter") as HTMLButtonElement).click();
    await bar.updateComplete;
    const items = Array.from(shadow(bar).querySelectorAll('[role="menu"] button')).map((b) => b.querySelector(".label")?.textContent);
    expect(items).toEqual(expect.arrayContaining(["Trace outline", "Preview path", "Start", "Pause", "Stop"]));
  });

  it("Ctrl+Enter starts, Ctrl+Shift+P pauses, Ctrl+, opens Settings", async () => {
    const { app } = await readyToPlot();
    expect(handleShortcut(app, new KeyboardEvent("keydown", { key: "Enter", ctrlKey: true }))).toBe(true);
    await settle();
    expect(app.state.plot.state).toBe("load_pen");
    await app.plotAction("continue");
    handleShortcut(app, new KeyboardEvent("keydown", { key: "P", ctrlKey: true, shiftKey: true }));
    await settle();
    expect(["pausing", "paused"]).toContain(app.state.plot.state);
    const other = await startApp();
    handleShortcut(other.app, new KeyboardEvent("keydown", { key: ",", ctrlKey: true }));
    expect(other.app.state.dialog?.kind).toBe("settings");
  });
});
```

Add to `tests/test_app_main.py`:

```python
from rosetta.app.main import AppPageGuard


class _Window:
    def __init__(self):
        self.url = None
        self.loaded = []

    def get_current_url(self):
        return self.url

    def load_url(self, url):
        self.loaded.append(url)


def test_the_window_goes_back_to_the_app_page():
    window = _Window()
    guard = AppPageGuard(window)
    window.url = "http://127.0.0.1:5000/index.html"
    guard.on_loaded()
    window.url = "http://127.0.0.1:5000/index.html#settings"
    guard.on_loaded()
    assert window.loaded == []
    window.url = "file:///C:/Users/student/drawing.svg"
    guard.on_loaded()
    assert window.loaded == ["http://127.0.0.1:5000/index.html"]
```

- [ ] **Step 2: Run them: FAIL**

- [ ] **Step 3: Menus (`menubar.ts`)**

File menu, after Import…:

```ts
          { label: "Settings…", shortcut: "Ctrl+,", run: () => app.openSettings() },
```

Plotter menu, after Move pen Home:

```ts
          "separator",
          { label: "Trace outline", reason: disabledReason("trace", s), run: () => void app.trace() },
          { label: "Preview path", reason: disabledReason("preview", s), run: () => app.startPreview() },
          "separator",
          { label: "Start", shortcut: "Ctrl+Enter", reason: disabledReason("start", s), run: () => void app.startPlot() },
          { label: "Pause", shortcut: "Ctrl+Shift+P", reason: disabledReason("pause", s), run: () => app.pause() },
          { label: "Stop", reason: disabledReason("stop", s), run: () => app.stopPlot() },
```

- [ ] **Step 4: Tools (`tools.ts`)**

In the Plotter group, after Set Home:

```ts
        { label: "Trace outline", iconName: "trace", reason: disabledReason("trace", s), run: () => void app.trace() },
        {
          label: "Preview path (Esc ends it)",
          iconName: "route",
          pressed: s.preview !== null,
          reason: s.preview ? null : disabledReason("preview", s),
          run: () => (s.preview ? app.endPreview() : app.startPreview()),
        },
```

Trace shows pressed while tracing: give the Trace entry `pressed: s.plot.state === "tracing"`.

- [ ] **Step 5: Shortcuts (`shortcuts.ts`)**

In the Ctrl branch, before `else return false;`:

```ts
    else if (key === "enter") void app.startPlot();
    else if (key === "p" && event.shiftKey) app.pause();
    else if (key === "p") {
      // Ctrl+P would open the WebView's print dialog: nothing to print here.
    } else if (key === ",") app.openSettings();
```

Add these rows to `SHORTCUT_HELP` in `app/shortcut-help.ts`, and change its comment to "in Plans 2b-1 and 2b-2":

```ts
  ["Settings", "Ctrl+,"],
  ["Start the plot", "Ctrl+Enter"],
  ["Pause the plot", "Ctrl+Shift+P"],
  ["End Preview path", "Esc"],
```

- [ ] **Step 6: Keep the window on the app's page (`main.py`)**

Add:

```python
class AppPageGuard:
    """pywebview hands the bridge (js_api) to any page the window shows. If the window ever leaves the
    app's own page (a link, or a file dropped where nothing catches it), take it back
    (plan2-notes "Lock navigation")."""

    def __init__(self, window):
        self._window = window
        self._home: str | None = None

    def on_loaded(self) -> None:
        url = self._window.get_current_url()
        if not url:
            return
        page = url.split("#")[0].split("?")[0]
        if self._home is None:
            self._home = page
        elif page != self._home:
            logger.warning("The window left the app's page for %s; going back", url)
            self._window.load_url(self._home)
```

In `main()`, after `window.events.loaded += lambda: _accept_dropped_files(window, api)`:

```python
    if entry:
        window.events.loaded += AppPageGuard(window).on_loaded
```

- [ ] **Step 7: Run everything**

Run:
- `npm test`, `npm run typecheck`, `npm run build`;
- `.venv\Scripts\python.exe -m pytest -q`;
- both smoke checks.

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add ui/src src/rosetta/app/main.py tests/test_app_main.py
git commit -m "feat: plot commands in the menus, tools and shortcuts; Settings… (Ctrl+,); the window stays on the app's page"
```

---

## Task 15: Docs, build, and the final checks

**Files:**
- Modify: `docs/bridge.md`, `docs/superpowers/specs/2026-10-07-rosetta-manager-ui-design.md`, `docs/superpowers/plan2-notes.md`

- [ ] **Step 1: Docs**

- **`docs/bridge.md`:**
  - In the `job_colors()` row, add: "`ink_bbox`, `clipped` and `empty` count hidden pens too; the plot leaves them out."
  - In `app_start()`'s reply, `advanced_options` becomes `{labels, ranges, choices, defaults}`.
- **The spec:**
  - Under the Status line, add: "**Built:** Plan 2b-1 (the window) and Plan 2b-2 (plotting, Preview path, Settings). **Plan 2b-3:** snapping, undo/redo, rulers, group scale/rotate, dock resizing, Quick Start."
  - In §4.7, add "(snapping options arrive with snapping, Plan 2b-3)" after "snapping on/off and snap distance".
- **`plan2-notes.md`**, "For Plan 2b": mark "Lock navigation in the WebView" as done: "Done in Plan 2b-2: `main.AppPageGuard` takes the window back to the app's page."

- [ ] **Step 2: Full checks**

Run, in order:
- `cd ui && npm test && npm run typecheck && npm run build`
- `.venv\Scripts\python.exe -m pytest -q`
- `.venv\Scripts\python.exe scripts\smoke_window.py`
- `.venv\Scripts\python.exe scripts\smoke_window.py --page`

Expected: all green. `--page` prints `{'ready': True, 'shell': True}`.

- [ ] **Step 3: Commit**

```bash
git add docs ui/dist
git commit -m "docs: Plan 2b-2 built; bridge notes; navigation lock done"
```

`ui/dist` is committed only if the repo already tracks it. Check with `git ls-files ui/dist | head -1`; if that prints nothing, leave `ui/dist` out of the `git add`.

## By hand, with Adam, on the plotter (not for agents)

After this plan, the desktop shortcut "Rosetta Plotter (preview)" runs the new window (it loads `ui/dist`). Do the spec §11.4 checklist through the window:
1. Status bar: the plotter connects and shows its model.
2. Set Home in two clicks.
3. Import a drawing, place it, and see the pen times.
4. Trace outline: the pen moves around the drawing, pen up.
5. Preview path plays.
6. Start: change pens when asked; Pause, Resume and Return Home work.
7. Stop asks first, then lifts the pen.
8. Pull the USB cable mid-plot: Continue, then It's in the corner, then Resume.
9. Done shows Plot another copy.
10. The drawing lands where the screen showed it, within ±1 mm.
