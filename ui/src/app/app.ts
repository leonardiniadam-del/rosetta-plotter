/**
 * Everything the window can do. Each action checks why it might not work yet (spec §6) and explains it in
 * the strip, calls Python (plotter requests one at a time), and updates the store.
 */
import { codeFromPicks, orientMatrix, screenToMachineDir, type Corner, type OrientationCode } from "../geometry/orientation";
import { BridgeError, type Client } from "../bridge/client";
import type { AdvancedValues, MachineStatus, PlacementData, PlotProgress, PlotStatus } from "../bridge/contract";
import { MAX_SCALE, pieceBox, resizeBox, rotateAboutCenter, type Point } from "../geometry/placement";
import { routeOf } from "../geometry/route";
import { formatLength, type Units } from "../geometry/units";
import { AT_REST } from "../state/plotting";
import { disabledReason, type Control } from "../state/reasons";
import { jobOf, pieceBoxOnPaper, plotRunning, selectedPieces, selectionBox } from "../state/selectors";
import { Store, type AppState, type Notice, type Tool, type ViewOptions } from "../state/store";

export const ONE_DRAWING = "Select one drawing to resize or turn it.";
export const STRETCH_TURNED = "Use W% and H% to stretch a turned drawing.";
export const TOO_BIG = "Drawings can be scaled up to 10000%.";
const RUNNING = "A plot is running.";
const NO_ROOM = "The margins leave no room on this paper.";
const OLD_FIRMWARE = "This plotter's firmware is old. You'll be asked for the model on each laptop.";
const MAX_MARGIN_MM = 50;
const MAX_PAPER_MM = 2000;
/** Half the smallest step a field shows (0.01 in), so a rounded limit typed back is accepted. */
const ROUNDING_MM = 0.127;
const INFO_MS = 8000;
const PREVIEW_TICK_MS = 33;
const DROP_MEMORY_MS = 3000;

/** Each plot.actions entry, and the bridge method it calls (bridge.md "Plot"). */
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
/** How long Stop waits for the plot to pause before it gives up. */
const STOP_WAIT_MS = 60_000;
/** The plot states Python's cancel() accepts (plotjob.PlotController.cancel). */
const CANCELLABLE = ["load_pen", "paused", "paused_at_home", "reconnect", "slide_home", "not_connected"];
/** The end of a plot's message when the pen isn't known to be Home (plotjob.HOME_UNKNOWN). */
const HOME_UNKNOWN = "Slide the pen Home before the next plot.";

export type ViewRequest = { kind: "fit-paper" } | { kind: "fit-reach" } | { kind: "zoom"; factor: number };

export interface AppOptions {
  colorsDelayMs: number;
  /** How long after the last change the plot is prepared again (spec §4.3). */
  prepareDelayMs: number;
  scanIntervalMs: number;
}

const DEFAULTS: AppOptions = { colorsDelayMs: 300, prepareDelayMs: 800, scanIntervalMs: 2000 };

/** What to tell the student about a failed call. */
function problemOf(error: unknown): { message: string; details: string } {
  if (error instanceof BridgeError) return { message: error.message, details: error.details };
  const details = error instanceof Error ? (error.stack ?? error.message) : String(error);
  return { message: "Something unexpected went wrong in the window.", details };
}

function fileName(path: string): string {
  return path.split(/[\\/]/).pop() ?? path;
}

const PICK_HOME = "Click the corner where HOME is on your plotter, as you face it.";
const PICK_X = "Click the corner the pen moves toward along X (along the rail).";

/** Holding a jog arrow (orientation spec §3): how long before it keeps going, and each move while held. */
export const HOLD_DELAY_MS = 300;
export const HOLD_MOVE_MM = 3;

export class App {
  /** The pointer's machine position; kept apart so moving the mouse only re-renders the status bar. */
  readonly cursor = new Store<{ point: Point | null }>({ point: null });
  /** Requests for the plate that aren't state: fit and zoom. */
  readonly viewRequests = new EventTarget();
  /** Where files from Windows were dropped on the plate, so the files_dropped event can place them there. */
  lastFileDrop: { point: Point; at: number } | null = null;
  /** The newest plot_progress event: its own store, so 10 updates a second re-render only what shows it. */
  readonly progress = new Store<{ value: PlotProgress | null }>({ value: null });

  private readonly options: AppOptions;
  private scanTimer: ReturnType<typeof setInterval> | null = null;
  private colorsTimer: ReturnType<typeof setTimeout> | null = null;
  private noticeTimer: ReturnType<typeof setTimeout> | null = null;
  private prepareTimer: ReturnType<typeof setTimeout> | null = null;
  /** Preview path's clock (seconds from the start of the plot): its own store, as it ticks 30 times a second. */
  readonly previewClock = new Store<{ t: number }>({ t: 0 });
  private previewTimer: ReturnType<typeof setInterval> | null = null;
  /** Counts plot_state events: a reply sent before the newest one has an older picture of the plot. */
  private plotEvents = 0;
  /** Plot actions sent and not answered yet: a double-click mustn't send one twice. */
  private readonly pendingActions = new Set<PlotAction>();
  /** Counts the times the plot went out of date; a prepare reply from an older count is dropped. */
  private prepareGeneration = 0;
  /** A prepare was due while another was running. */
  private prepareAgain = false;
  /** Calls that change what's on the paper run one after another, in the order they were asked for. */
  private edits: Promise<unknown> = Promise.resolve();
  /** The newest placement still to be sent, per piece; only that one goes when the previous reply is in. */
  private readonly wanted = new Map<string, PlacementData>();
  private readonly sending = new Map<string, Promise<void>>();
  /** The old-firmware notice is said once per session. */
  private oldFirmwareSaid = false;

  constructor(
    readonly store: Store<AppState>,
    readonly client: Client,
    options: Partial<AppOptions> = {},
  ) {
    this.options = { ...DEFAULTS, ...options };
  }

  get state(): AppState {
    return this.store.state;
  }

  // Start-up, events and problems.

  async start(): Promise<void> {
    const start = await this.client.call("app_start");
    const { jobs, pieces } = await this.client.call("job_list");
    this.store.update({
      ready: true,
      start,
      units: start.settings.units,
      machine: start.machine,
      material: start.material,
      paper: start.settings.paper,
      margin: start.settings.margin_mm,
      plot: start.plot,
      advanced: start.settings.advanced,
      orientation: start.orientation,
      jobs,
      pieces,
    });
    this.refreshColors();
    this.schedulePrepare();
    this.scanTimer = setInterval(() => {
      if (this.state.machine.state === "no_plotter") void this.scan();
    }, this.options.scanIntervalMs);
    if (start.machine.state === "no_plotter") await this.scan();
    this.requestView({ kind: "fit-paper" });
  }

  stop(): void {
    if (this.scanTimer) clearInterval(this.scanTimer);
    if (this.colorsTimer) clearTimeout(this.colorsTimer);
    if (this.noticeTimer) clearTimeout(this.noticeTimer);
    if (this.prepareTimer) clearTimeout(this.prepareTimer);
    this.scanTimer = this.colorsTimer = this.noticeTimer = this.prepareTimer = null;
    this.prepareAgain = false;
    if (this.previewTimer) clearInterval(this.previewTimer);
    this.previewTimer = null;
  }

  onEvent(name: string, data: unknown): void {
    if (name === "plot_state") {
      this.plotEvents += 1;
      this.onPlotState(data as PlotStatus);
    } else if (name === "plot_progress") {
      this.progress.update({ value: data as PlotProgress });
    } else if (name === "close_requested") {
      this.askToClose();
    } else if (name === "files_dropped") {
      const recent = this.lastFileDrop && Date.now() - this.lastFileDrop.at < DROP_MEMORY_MS;
      const point = recent && this.lastFileDrop ? this.lastFileDrop.point : undefined;
      this.lastFileDrop = null;
      void this.importFiles((data as { paths: string[] }).paths, point);
    }
  }

  notify(notice: Notice): void {
    if (this.noticeTimer) clearTimeout(this.noticeTimer);
    this.noticeTimer = null;
    this.store.update({ notice });
    if (notice.kind === "info" && !notice.actions?.length && !notice.keep) this.noticeTimer = setTimeout(() => this.dismissNotice(), INFO_MS);
  }

  dismissNotice(): void {
    this.store.update({ notice: null });
  }

  fail(error: unknown): void {
    this.notify({ kind: "error", ...problemOf(error) });
  }

  /** Say why a greyed-out control can't work yet. */
  explain(reason: string): void {
    this.notify({ kind: "info", message: reason });
  }

  private blocked(control: Control): boolean {
    const reason = disabledReason(control, this.state);
    if (reason) this.explain(reason);
    return reason !== null;
  }

  private async attempt<T>(work: () => Promise<T>): Promise<T | undefined> {
    try {
      return await work();
    } catch (error) {
      this.fail(error);
      return undefined;
    }
  }

  /** A plotter request; afterwards the plotter's state is refreshed either way (bridge.md). */
  private async plotterAction(work: () => Promise<{ machine: MachineStatus }>): Promise<boolean> {
    try {
      this.setMachine((await work()).machine);
      return true;
    } catch (error) {
      this.fail(error);
      await this.scan();
      return false;
    }
  }

  // The plotter.

  setMachine(machine: MachineStatus): void {
    const previous = this.state.machine;
    this.store.update((s) => ({ machine, homing: s.homing && machine.state === "not_homed" }));
    // The model became known or changed, or the plotter came or went: the plot is prepared for it again.
    if (machine.model !== previous.model || (previous.state === "no_plotter") !== (machine.state === "no_plotter")) {
      this.schedulePrepare();
    }
    if (machine.old_firmware && !this.oldFirmwareSaid) {
      this.oldFirmwareSaid = true;
      this.notify({ kind: "info", message: OLD_FIRMWARE });
    }
  }

  /** Look for the plotter. No plotter is normal, so this never shows a problem. */
  async scan(): Promise<void> {
    try {
      const reply = await this.client.call("plotter_scan");
      this.setMachine(reply.machine);
      this.takeOrientation(reply.orientation);
    } catch {
      // The next scan tries again.
    }
  }

  /** A plotter's saved orientation came back with it. */
  private takeOrientation(code: OrientationCode | undefined): void {
    if (code && code !== this.state.orientation) this.store.update({ orientation: code });
  }

  /** Turn the plate to match how the plotter sits. Only the view changes, never the plot. */
  async setPlotterOrientation(code: OrientationCode): Promise<void> {
    if (this.blocked("orientation")) return;
    const before = this.state.orientation;
    this.store.update({ orientation: code });
    const reply = await this.attempt(() => this.client.call("set_orientation", code));
    if (!reply) this.store.update({ orientation: before });
  }

  /** Set plotter orientation: pick HOME's corner on the plate, then the corner X runs toward. */
  startOrienting(): void {
    if (this.blocked("orientation")) return;
    this.store.update({ orienting: { home: null } });
    this.notify({ kind: "info", message: PICK_HOME, keep: true });
    this.requestView({ kind: "fit-reach" }); // the picks sit on the reach's corners: show all four
  }

  async pickCorner(corner: Corner): Promise<void> {
    const picking = this.state.orienting;
    if (!picking) return;
    if (!picking.home) {
      this.store.update({ orienting: { home: corner } });
      this.notify({ kind: "info", message: PICK_X, keep: true });
      return;
    }
    const code = codeFromPicks(picking.home, corner);
    if (!code) return; // not next to HOME's corner: keep waiting
    this.cancelOrienting();
    await this.setPlotterOrientation(code);
  }

  cancelOrienting(): void {
    if (!this.state.orienting) return;
    this.store.update((s) => ({
      orienting: null,
      notice: s.notice?.message === PICK_HOME || s.notice?.message === PICK_X ? null : s.notice,
    }));
  }

  resetOrientation(): Promise<void> {
    return this.setPlotterOrientation("nw-h");
  }

  async identify(model: number, penlift: number, label: string): Promise<void> {
    const identified = await this.plotterAction(async () => {
      const reply = await this.client.hardware("plotter_identify", model, penlift, label);
      this.takeOrientation(reply.orientation);
      return reply;
    });
    if (!identified) return;
    this.store.update({ dialog: null });
    this.refreshColors();
    // The plotter keeps the label in its nickname, which may be shorter than what was typed.
    const stored = this.state.machine.label ?? label;
    const shortened = stored !== label.trim() ? " (the plotter keeps a shorter name)" : "";
    this.notify({
      kind: "info",
      message: this.state.machine.old_firmware
        ? "Saved on this laptop. This plotter's firmware is old, so other laptops will ask for its model too."
        : `Saved. This plotter is now named "${stored}"${shortened}.`,
    });
  }

  /** Set Home: the first click lets go of the motors; the second confirms the pen is in the HOME corner. */
  async setHome(): Promise<void> {
    if (this.blocked("setHome")) return;
    if (!this.state.homing) {
      if (await this.plotterAction(() => this.client.hardware("plotter_motors_off"))) this.store.update({ homing: true });
      return;
    }
    this.store.update({ homing: false });
    await this.plotterAction(() => this.client.hardware("plotter_set_home"));
  }

  cancelHoming(): void {
    this.store.update({ homing: false });
  }

  /** A direction on screen as a machine direction, for the plotter's orientation. */
  machineDirection(dx: number, dy: number): Point {
    const [x, y] = screenToMachineDir(orientMatrix(this.state.orientation), [dx, dy]);
    return [x + 0, y + 0]; // + 0 turns -0 into 0
  }

  /** Move the pen one step (pen up) in a screen direction: (1, 0) is right on screen. */
  async jog(dx: number, dy: number): Promise<void> {
    if (this.blocked("move")) return;
    const step = this.state.jogStep;
    const [x, y] = this.machineDirection(dx, dy);
    await this.plotterAction(() => this.client.hardware("plotter_jog", x * step, y * step));
  }

  /** The hold under way, if any: a new press or a release replaces it, which ends its loop. */
  private holding: object | null = null;

  /**
   * Press on a jog arrow: one step now, then, while still held after HOLD_DELAY_MS, moves of
   * HOLD_MOVE_MM one at a time. It stops on release, on a problem, or when the pen stops moving
   * (the reach). Directions are on screen, as for jog().
   */
  jogHold(dx: number, dy: number): void {
    this.jogRelease();
    if (this.blocked("move")) return;
    const hold = {};
    this.holding = hold;
    void (async () => {
      await this.jog(dx, dy);
      await new Promise((done) => setTimeout(done, HOLD_DELAY_MS));
      let last = this.state.machine.position;
      while (this.holding === hold && disabledReason("move", this.state) === null) {
        const [x, y] = this.machineDirection(dx, dy);
        const moved = await this.plotterAction(() => this.client.hardware("plotter_jog", x * HOLD_MOVE_MM, y * HOLD_MOVE_MM));
        const now = this.state.machine.position;
        if (!moved || !now || (last && now[0] === last[0] && now[1] === last[1])) break;
        last = now;
      }
      if (this.holding === hold) this.holding = null;
    })();
  }

  /** Let go of a jog arrow: no new move is sent; one already on its way finishes. */
  jogRelease(): void {
    this.holding = null;
  }

  async movePenTo([x, y]: Point): Promise<void> {
    if (this.blocked("move")) return;
    await this.plotterAction(() => this.client.hardware("plotter_goto", x, y));
  }

  movePenHome(): Promise<void> {
    return this.movePenTo([0, 0]);
  }

  async pen(down: boolean): Promise<void> {
    if (this.blocked("move")) return;
    await this.plotterAction(() => this.client.hardware("plotter_pen", down));
  }

  async testMark(): Promise<void> {
    if (this.blocked("move")) return;
    await this.plotterAction(() => this.client.hardware("plotter_test_mark"));
  }

  /** The pen-height slider and pen type: only the newest value is sent while one is on its way. */
  async setPen(penDown: number, penType: string): Promise<void> {
    this.store.update((s) => ({ machine: { ...s.machine, pen_down: penDown, pen_type: penType } }));
    try {
      const reply = await this.client.latest("pen", "pen_set", penDown, penType);
      if (reply) this.setMachine(reply.machine);
    } catch (error) {
      this.fail(error);
      await this.scan();
    }
  }

  setJogStep(step: 1 | 10): void {
    this.store.update({ jogStep: step });
  }

  openModelDialog(): void {
    if (this.blocked("model")) return;
    this.store.update({ dialog: { kind: "model" } });
  }

  showDialog(kind: "shortcuts" | "about"): void {
    this.store.update({ dialog: { kind } });
  }

  closeDialog(): void {
    this.store.update({ dialog: null });
  }

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

  async copyDiagnostics(): Promise<void> {
    const reply = await this.attempt(() => this.client.call("diagnostics"));
    if (!reply) return;
    try {
      await navigator.clipboard.writeText(reply.text);
      this.notify({ kind: "info", message: "Diagnostics copied. Paste them into a message to whoever is helping you." });
    } catch {
      this.store.update({ dialog: { kind: "text", title: "Diagnostics", text: reply.text } });
    }
  }

  async exit(): Promise<void> {
    await this.attempt(() => this.client.call("quit_confirmed"));
  }

  // Units, tools and the view.

  async setUnits(units: Units): Promise<void> {
    this.store.update({ units });
    await this.attempt(() => this.client.call("set_units", units));
  }

  setTool(tool: Tool): void {
    if (this.state.preview) this.endPreview();
    this.store.update({ tool });
  }

  toggleView(key: keyof ViewOptions): void {
    this.store.update((s) => ({ view: { ...s.view, [key]: !s.view[key] } }));
  }

  toggleLink(): void {
    this.store.update((s) => ({ linkScale: !s.linkScale }));
  }

  requestView(request: ViewRequest): void {
    this.viewRequests.dispatchEvent(new CustomEvent<ViewRequest>("view", { detail: request }));
  }

  // The paper.

  async setPaper(
    size: string,
    orientation: "landscape" | "portrait",
    customWidth: number | null = null,
    customHeight: number | null = null,
  ): Promise<void> {
    if (this.blocked("paper")) return;
    if (size === "custom") {
      const usable = (v: number | null) => v !== null && Number.isFinite(v) && v > 0 && v <= MAX_PAPER_MM;
      if (!usable(customWidth) || !usable(customHeight)) {
        return this.explain(`Paper width and height must be above 0 and at most ${formatLength(MAX_PAPER_MM, this.state.units, true)}.`);
      }
    }
    const { x, y } = this.state.material;
    const reply = await this.attempt(() => this.client.call("material_set", size, orientation, customWidth, customHeight, x, y));
    if (!reply) return;
    const custom = size === "custom";
    this.store.update({
      material: reply.material,
      paper: {
        size,
        orientation,
        custom_width_mm: custom ? reply.material.width : null,
        custom_height_mm: custom ? reply.material.height : null,
      },
    });
    this.refreshColors();
  }

  /** The orientation buttons swap the paper's sides; the drawings stay where they are. */
  async setOrientation(orientation: "landscape" | "portrait"): Promise<void> {
    if (this.blocked("paper")) return;
    const { paper, material } = this.state;
    if (paper.orientation === orientation) return;
    if (paper.size === "custom") await this.setPaper("custom", orientation, material.height, material.width);
    else await this.setPaper(paper.size, orientation);
  }

  async movePaper(x: number, y: number): Promise<void> {
    if (this.blocked("paper")) return;
    const p = this.state.paper;
    const reply = await this.attempt(() =>
      this.client.call("material_set", p.size, p.orientation, p.custom_width_mm, p.custom_height_mm, x, y),
    );
    if (!reply) return;
    this.store.update({ material: reply.material });
    this.refreshColors();
  }

  async markCorner(): Promise<void> {
    if (this.blocked("paper") || this.blocked("markCorner")) return;
    const reply = await this.attempt(() => this.client.call("material_mark_corner"));
    if (!reply) return;
    this.store.update({ material: reply.material });
    this.refreshColors();
  }

  async setMargin(margin: number): Promise<void> {
    if (this.blocked("paper")) return;
    // The limit is shown rounded ("1.97 in" is 50.04 mm): typing the shown limit means the limit.
    if (margin > MAX_MARGIN_MM && margin - MAX_MARGIN_MM <= ROUNDING_MM) margin = MAX_MARGIN_MM;
    if (!(margin >= 0 && margin <= MAX_MARGIN_MM)) {
      return this.explain(`The margin must be from 0 to ${formatLength(MAX_MARGIN_MM, this.state.units, true)}.`);
    }
    const reply = await this.attempt(() => this.client.call("set_margin", margin));
    if (reply) this.store.update({ margin: reply.margin_mm });
  }

  async rotatePaper(): Promise<void> {
    if (this.blocked("rotatePaper")) return;
    const reply = await this.attempt(() => this.inOrder(() => this.client.call("paper_rotate")));
    if (!reply) return;
    this.store.update({ material: reply.material, paper: reply.paper, pieces: reply.pieces });
    this.refreshColors();
  }

  // Jobs.

  /** Import files into the Jobs list: from Windows' Open dialog, or the given paths. Placed at `dropAt` if given. */
  async importFiles(paths?: string[], dropAt?: Point): Promise<void> {
    let files = paths;
    if (!files) {
      const chosen = await this.attempt(() => this.client.call("artwork_choose"));
      if (!chosen) return;
      files = chosen.paths;
    }
    for (const path of files) {
      const counted = await this.attempt(() => this.client.call("artwork_pages", path));
      if (!counted) continue;
      let page = 0;
      if (counted.pages > 1) {
        const chosen = await this.askPage(fileName(path), counted.pages);
        if (chosen === null) continue;
        page = chosen;
      }
      const reply = await this.attempt(() => this.client.call("job_import", path, page));
      if (!reply) continue;
      this.store.update((s) => ({ jobs: [...s.jobs, reply.job] }));
      if (dropAt) await this.placeJob(reply.job.id, dropAt);
    }
  }

  /** Which page of a many-page file to import (0-based), or null if cancelled. */
  askPage(name: string, pages: number): Promise<number | null> {
    return new Promise((resolve) => {
      this.store.update({
        dialog: {
          kind: "pages",
          name,
          pages,
          resolve: (page) => {
            this.store.update({ dialog: null });
            resolve(page);
          },
        },
      });
    });
  }

  /** Where double-clicking a job puts its corner nearest HOME: the paper's corner nearest Home, inset by the margin. */
  marginCorner(): Point {
    return [this.state.margin, this.state.margin];
  }

  async placeJob(jobId: string, at: Point = this.marginCorner()): Promise<void> {
    if (plotRunning(this.state)) return this.explain(RUNNING);
    const reply = await this.attempt(() => this.inOrder(() => this.client.call("job_place", jobId, at[0], at[1])));
    if (!reply) return;
    this.store.update((s) => ({ pieces: [...s.pieces, reply.piece], selection: [reply.piece.id] }));
    this.refreshColors();
  }

  /** Remove a job; with copies on the paper, ask first in the strip (spec §4.2). */
  removeJob(jobId: string): void {
    const job = this.state.jobs.find((j) => j.id === jobId);
    if (!job) return;
    if (plotRunning(this.state)) return this.explain(RUNNING);
    const copies = this.state.pieces.filter((p) => p.job_id === jobId).length;
    const remove = async () => {
      this.dismissNotice();
      const reply = await this.attempt(() => this.inOrder(() => this.client.call("job_remove", jobId)));
      if (!reply) return;
      const gone = new Set(reply.removed_pieces);
      this.store.update((s) => ({
        jobs: s.jobs.filter((j) => j.id !== jobId),
        pieces: s.pieces.filter((p) => !gone.has(p.id)),
        selection: s.selection.filter((id) => !gone.has(id)),
      }));
      this.refreshColors();
    };
    if (copies === 0) {
      void remove();
      return;
    }
    this.notify({
      kind: "warning",
      message: `Remove ${job.name} and its ${copies} ${copies === 1 ? "copy" : "copies"} on the paper?`,
      actions: [
        { label: "Remove", run: () => void remove() },
        { label: "Keep", run: () => this.dismissNotice() },
      ],
    });
  }

  /** The job behind the selected drawing (for Object › Remove job from list). */
  selectedJobId(): string | null {
    return selectedPieces(this.state)[0]?.job_id ?? null;
  }

  // Selection.

  select(ids: string[]): void {
    this.store.update({ selection: ids });
  }

  toggleSelect(id: string): void {
    this.store.update((s) => ({
      selection: s.selection.includes(id) ? s.selection.filter((x) => x !== id) : [...s.selection, id],
    }));
  }

  selectAll(): void {
    this.store.update((s) => ({ selection: s.pieces.map((p) => p.id) }));
  }

  deselect(): void {
    this.store.update({ selection: [] });
  }

  // Placing and editing drawings.

  /** Show a placement while dragging, without telling Python yet. */
  previewPlacement(id: string, placement: PlacementData): void {
    this.store.update((s) => ({ pieces: s.pieces.map((p) => (p.id === id ? { ...p, placement } : p)) }));
  }

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

  async setPlacement(id: string, placement: PlacementData): Promise<void> {
    this.previewPlacement(id, placement);
    await this.commitPlacement(id);
  }

  async moveSelectionBy(dx: number, dy: number): Promise<void> {
    if (this.blocked("arrange")) return;
    for (const piece of selectedPieces(this.state)) {
      await this.setPlacement(piece.id, { ...piece.placement, x: piece.placement.x + dx, y: piece.placement.y + dy });
    }
  }

  /** Typed X or Y for the selection's box (null leaves that one). */
  async moveSelectionTo(x: number | null, y: number | null): Promise<void> {
    const box = selectionBox(this.state);
    if (!box) {
      this.blocked("arrange");
      return;
    }
    await this.moveSelectionBy(x === null ? 0 : x - box.x, y === null ? 0 : y - box.y);
  }

  private single() {
    if (this.blocked("arrange")) return null;
    const pieces = selectedPieces(this.state);
    if (pieces.length !== 1) {
      this.explain(ONE_DRAWING);
      return null;
    }
    const job = jobOf(this.state, pieces[0]);
    return job ? { piece: pieces[0], job } : null;
  }

  async resizeSelected(size: { width?: number; height?: number }): Promise<void> {
    const one = this.single();
    if (!one) return;
    const next = resizeBox(one.job.width_mm, one.job.height_mm, one.piece.placement, size, this.state.linkScale);
    if (!next) return this.explain(STRETCH_TURNED);
    await this.setPlacement(one.piece.id, next);
  }

  /** W% / H% (or one Scale % while linked); the corner nearest HOME stays put. */
  async setScale(scale: number, scaleY: number): Promise<void> {
    const one = this.single();
    if (!one) return;
    await this.setPlacement(one.piece.id, { ...one.piece.placement, scale, scale_y: scaleY });
  }

  async rotateSelectedTo(angle: number): Promise<void> {
    const one = this.single();
    if (!one) return;
    await this.setPlacement(one.piece.id, rotateAboutCenter(one.job.width_mm, one.job.height_mm, one.piece.placement, angle));
  }

  /** Rotate 90°: each selected drawing turns about its own center. */
  async rotateSelectionBy(delta: number): Promise<void> {
    if (this.blocked("arrange")) return;
    for (const piece of selectedPieces(this.state)) {
      const job = jobOf(this.state, piece);
      if (!job) continue;
      await this.setPlacement(piece.id, rotateAboutCenter(job.width_mm, job.height_mm, piece.placement, piece.placement.rotation + delta));
    }
  }

  async centerSelection(): Promise<void> {
    const box = selectionBox(this.state);
    if (!box) {
      this.blocked("arrange");
      return;
    }
    const { width, height } = this.state.material;
    await this.moveSelectionBy((width - box.width) / 2 - box.x, (height - box.height) / 2 - box.y);
  }

  /** Fit to paper: shrink (never enlarge) to fit inside the margins, then center (spec §4.2). */
  async fitSelection(): Promise<void> {
    const one = this.single();
    if (!one) return;
    const { width, height } = this.state.material;
    const margin = this.state.margin;
    const box = pieceBoxOnPaper(this.state, one.piece);
    const factor = Math.min(1, (width - 2 * margin) / box.width, (height - 2 * margin) / box.height);
    if (!(factor > 0)) return this.explain(NO_ROOM);
    const p = one.piece.placement;
    const scaled = { ...p, scale: p.scale * factor, scale_y: p.scale_y * factor };
    const size = pieceBox(one.job.width_mm, one.job.height_mm, scaled);
    await this.setPlacement(one.piece.id, { ...scaled, x: (width - size.width) / 2, y: (height - size.height) / 2 });
  }

  async duplicateSelection(): Promise<void> {
    if (this.blocked("arrange")) return;
    const copies: string[] = [];
    for (const piece of selectedPieces(this.state)) {
      const reply = await this.attempt(() => this.inOrder(() => this.client.call("piece_duplicate", piece.id)));
      if (!reply) continue;
      copies.push(reply.piece.id);
      this.store.update((s) => {
        const pieces = [...s.pieces];
        pieces.splice(pieces.findIndex((p) => p.id === piece.id) + 1, 0, reply.piece);
        return { pieces };
      });
    }
    if (copies.length > 0) this.select(copies);
    this.refreshColors();
  }

  async deleteSelection(): Promise<void> {
    if (this.blocked("arrange")) return;
    for (const id of [...this.state.selection]) {
      const reply = await this.attempt(() => this.inOrder(() => this.client.call("piece_delete", id)));
      if (!reply) continue;
      this.store.update((s) => ({ pieces: s.pieces.filter((p) => p.id !== id), selection: s.selection.filter((x) => x !== id) }));
    }
    this.refreshColors();
  }

  // Pens.

  /** Ask Python for the pen colors, a moment after the last change (spec §4.3). */
  refreshColors(): void {
    this.schedulePrepare();
    if (this.colorsTimer) clearTimeout(this.colorsTimer);
    this.colorsTimer = setTimeout(() => {
      this.colorsTimer = null;
      void this.attempt(async () => {
        const reply = await this.client.call("job_colors");
        this.store.update({ colors: reply.colors });
      });
    }, this.options.colorsDelayMs);
  }

  async setPenVisible(color: string, visible: boolean): Promise<void> {
    this.store.update((s) => ({ colors: s.colors.map((c) => (c.color === color ? { ...c, visible } : c)) }));
    await this.attempt(() => this.client.call("set_pen_visible", color, visible));
    this.refreshColors();
  }

  // Preparing the plot (spec §4.3).

  /** Plan the plot (times and path) a moment after the last change, whenever it's out of date. */
  schedulePrepare(): void {
    // Whatever prepare is on its way now is out of date (onPlotState's idle comes through here too).
    this.prepareGeneration += 1;
    if (this.prepareTimer) clearTimeout(this.prepareTimer);
    this.prepareTimer = setTimeout(() => {
      this.prepareTimer = null;
      void this.prepare();
    }, this.options.prepareDelayMs);
  }

  /** Idle, or at rest without the page knowing the plan (a reload finds Python already prepared). */
  private canPrepare(): boolean {
    const s = this.state;
    const outOfDate = s.plot.state === "idle" || (AT_REST.includes(s.plot.state) && s.summary === null);
    return outOfDate && s.pieces.length > 0 && s.machine.model !== null && s.machine.state !== "no_plotter";
  }

  async prepare(): Promise<void> {
    if (this.state.preparing) {
      // Python refuses a second prepare: ask again once this one is over.
      this.prepareAgain = true;
      return;
    }
    if (!this.canPrepare()) return;
    const generation = this.prepareGeneration;
    this.store.update({ preparing: true, prepareProblem: null });
    try {
      const { summary } = await this.client.call("plot_prepare");
      // A change overtook this reply (its idle event can arrive first): the plan is old, so it's dropped.
      if (generation === this.prepareGeneration) this.store.update({ summary });
    } catch (error) {
      // Shown on Start, not in the strip: preparing is automatic. A change while preparing makes Python
      // go back to idle, and that plot_state event prepares again.
      const message = error instanceof BridgeError ? error.message : "The plot couldn't be prepared.";
      if (generation === this.prepareGeneration) this.store.update({ summary: null, prepareProblem: message });
    } finally {
      this.store.update({ preparing: false });
      if (this.prepareAgain) {
        this.prepareAgain = false;
        this.schedulePrepare();
      }
    }
  }

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

  // The plot's state (spec §4.4).

  private onPlotState(plot: PlotStatus): void {
    const before = this.state.plot.state;
    this.store.update((s) => ({ plot, summary: plot.state === "idle" ? null : s.summary }));
    if (AT_REST.includes(plot.state)) this.progress.update({ value: null });
    if (plot.state === "idle") this.schedulePrepare();
    // The route is gone (the plot changed) or a real plot has begun.
    if (plot.state === "idle" || plotRunning(this.state)) this.endPreview();
    // A question about the running plot means nothing once it's over.
    const asked = this.state.dialog;
    if (AT_REST.includes(plot.state) && asked?.kind === "confirm" && asked.plot) this.closeDialog();
    this.showPlotNotice(plot, before);
    if (AT_REST.includes(plot.state) && !AT_REST.includes(before)) void this.refreshPlot();
  }

  /** Ask Python where the plot and the plotter are (after a refused call, or when a plot ends). */
  async refreshPlot(): Promise<void> {
    const seen = this.plotEvents;
    try {
      const reply = await this.client.call("plot_status");
      this.setMachine(reply.machine);
      if (seen === this.plotEvents && reply.plot.state !== this.state.plot.state) this.onPlotState(reply.plot);
    } catch {
      await this.scan();
    }
  }

  /** The strip for plot states that need the student (spec §4.4), and the result when a plot ends. */
  private showPlotNotice(plot: PlotStatus, before: string): void {
    const notice = this.recoveryNotice(plot.state, plot.message, plot.details);
    if (notice) {
      this.notify(notice);
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
      const kind = plot.details ? "error" : plot.message.includes(HOME_UNKNOWN) ? "warning" : "info";
      this.notify({ kind, source: "plot", message: plot.message, details: plot.details || undefined });
    }
  }

  /** The strip's recovery buttons for a plot state that needs the student, or null for other states. */
  private recoveryNotice(state: string, message: string, details: string): Notice | null {
    const run = (action: PlotAction) => () => void this.plotAction(action);
    const recoveries: Record<string, [Notice["kind"], string, PlotAction]> = {
      reconnect: ["warning", "Continue", "reconnect"],
      slide_home: ["warning", "It's in the corner", "rehomed"],
      not_connected: ["error", "Retry", "retry"],
    };
    const recovery = recoveries[state];
    if (!recovery) return null;
    const [kind, label, action] = recovery;
    const actions = [
      { label, run: run(action) },
      { label: "Cancel plot", run: run("cancel") },
    ];
    return { kind, source: "plot", message, details: details || undefined, actions };
  }

  // Plotting (spec §4.4).

  /** One of plot.actions. Pause never waits behind another plotter request; the rest take their turn. */
  async plotAction(action: PlotAction): Promise<boolean> {
    if (this.pendingActions.has(action)) return false; // a double-click: the first is still on its way
    this.pendingActions.add(action);
    const method = ACTION_METHODS[action];
    const seen = this.plotEvents;
    try {
      const reply = action === "pause" ? await this.client.call(method) : await this.client.hardware(method);
      this.setMachine(reply.machine);
      // A plot_state event that came while waiting is newer than the reply's picture of the plot.
      if (seen === this.plotEvents && reply.plot.state !== this.state.plot.state) this.onPlotState(reply.plot);
      return true;
    } catch (error) {
      this.fail(error);
      await this.refreshPlot();
      // A refused recovery step: its buttons stay, with the reason in place of the plot's message.
      const problem = problemOf(error);
      const notice = this.recoveryNotice(this.state.plot.state, problem.message, problem.details);
      if (notice) this.notify(notice);
      return false;
    } finally {
      this.pendingActions.delete(action);
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

  /** Stop: a trace stops at once; a plot asks first, then pauses and is cancelled (bridge.md "Stopping a plot"). */
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
        plot: true,
        run: () => void this.pauseThenCancel(),
      },
    });
  }

  /** Cancel plot from the plot bar (paused): asks first, like Stop, since the plot can't be resumed. */
  cancelPlot(): void {
    this.store.update({
      dialog: {
        kind: "confirm",
        title: "Cancel the plot?",
        message: "This plot can't be resumed.",
        confirm: "Cancel plot",
        cancel: "Keep plot",
        plot: true,
        run: () => {
          this.closeDialog();
          void this.plotAction("cancel");
        },
      },
    });
  }

  private async pauseThenCancel(): Promise<void> {
    this.closeDialog();
    if (!(await this.plotAction("pause"))) return;
    let state: string;
    try {
      // Paused, or anywhere else Python can cancel from: a pen change (the pen finished as the pause came),
      // or a recovery state (the cable was pulled while pausing). At rest, there's nothing left to stop.
      state = await this.waitForPlot([...CANCELLABLE, ...AT_REST], STOP_WAIT_MS);
    } catch (error) {
      // Only reached while still plotting, pausing or homing: no other strip or dialog is showing.
      this.fail(error);
      return;
    }
    if (CANCELLABLE.includes(state)) await this.plotAction("cancel");
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

  /** The window was closed mid-plot (close_requested): ask, then close; Python pauses the plot first (spec §4.4). */
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
          // quit_confirmed pauses the plot first, and its reply may never come (the window closes).
          this.notify({ kind: "info", message: "Lifting the pen and closing…", keep: true });
          void this.exit();
        },
      },
    });
  }
}
