/**
 * Everything the window can do. Each action checks why it might not work yet (spec §6) and explains it in
 * the strip, calls Python (plotter requests one at a time), and updates the store.
 */
import { BridgeError, type Client } from "../bridge/client";
import type { MachineStatus, PlacementData, PlotStatus } from "../bridge/contract";
import { MAX_SCALE, pieceBox, resizeBox, rotateAboutCenter, type Point } from "../geometry/placement";
import { formatLength, type Units } from "../geometry/units";
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
const DROP_MEMORY_MS = 3000;

export type ViewRequest = { kind: "fit-paper" } | { kind: "fit-reach" } | { kind: "zoom"; factor: number };

export interface AppOptions {
  colorsDelayMs: number;
  scanIntervalMs: number;
}

const DEFAULTS: AppOptions = { colorsDelayMs: 300, scanIntervalMs: 2000 };

function fileName(path: string): string {
  return path.split(/[\\/]/).pop() ?? path;
}

export class App {
  /** The pointer's machine position; kept apart so moving the mouse only re-renders the status bar. */
  readonly cursor = new Store<{ point: Point | null }>({ point: null });
  /** Requests for the plate that aren't state: fit and zoom. */
  readonly viewRequests = new EventTarget();
  /** Where files from Windows were dropped on the plate, so the files_dropped event can place them there. */
  lastFileDrop: { point: Point; at: number } | null = null;

  private readonly options: AppOptions;
  private scanTimer: ReturnType<typeof setInterval> | null = null;
  private colorsTimer: ReturnType<typeof setTimeout> | null = null;
  private noticeTimer: ReturnType<typeof setTimeout> | null = null;
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
      jobs,
      pieces,
    });
    this.refreshColors();
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
    this.scanTimer = this.colorsTimer = this.noticeTimer = null;
  }

  onEvent(name: string, data: unknown): void {
    if (name === "plot_state") {
      this.store.update({ plot: data as PlotStatus });
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
    if (notice.kind === "info") this.noticeTimer = setTimeout(() => this.dismissNotice(), INFO_MS);
  }

  dismissNotice(): void {
    this.store.update({ notice: null });
  }

  fail(error: unknown): void {
    if (error instanceof BridgeError) {
      this.notify({ kind: "error", message: error.message, details: error.details });
    } else {
      const details = error instanceof Error ? (error.stack ?? error.message) : String(error);
      this.notify({ kind: "error", message: "Something unexpected went wrong in the window.", details });
    }
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
    this.store.update((s) => ({ machine, homing: s.homing && machine.state === "not_homed" }));
    if (machine.old_firmware && !this.oldFirmwareSaid) {
      this.oldFirmwareSaid = true;
      this.notify({ kind: "info", message: OLD_FIRMWARE });
    }
  }

  /** Look for the plotter. No plotter is normal, so this never shows a problem. */
  async scan(): Promise<void> {
    try {
      this.setMachine((await this.client.call("plotter_scan")).machine);
    } catch {
      // The next scan tries again.
    }
  }

  async identify(model: number, penlift: number, label: string): Promise<void> {
    if (!(await this.plotterAction(() => this.client.hardware("plotter_identify", model, penlift, label)))) return;
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

  async jog(dx: number, dy: number): Promise<void> {
    if (this.blocked("move")) return;
    const step = this.state.jogStep;
    await this.plotterAction(() => this.client.hardware("plotter_jog", dx * step, dy * step));
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
    const { paper, material } = this.state;
    if (paper.orientation === orientation) return;
    if (paper.size === "custom") await this.setPaper("custom", orientation, material.height, material.width);
    else await this.setPaper(paper.size, orientation);
  }

  async movePaper(x: number, y: number): Promise<void> {
    const p = this.state.paper;
    const reply = await this.attempt(() =>
      this.client.call("material_set", p.size, p.orientation, p.custom_width_mm, p.custom_height_mm, x, y),
    );
    if (!reply) return;
    this.store.update({ material: reply.material });
    this.refreshColors();
  }

  async markCorner(): Promise<void> {
    if (this.blocked("markCorner")) return;
    const reply = await this.attempt(() => this.client.call("material_mark_corner"));
    if (!reply) return;
    this.store.update({ material: reply.material });
    this.refreshColors();
  }

  async setMargin(margin: number): Promise<void> {
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

  /** Where double-clicking a job puts its top-left: the paper's corner nearest Home, inset by the margin. */
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

  /** W% / H% (or one Scale % while linked); the top-left stays put. */
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
}
