/**
 * FakeApi: a stand-in for Python that follows docs/bridge.md, for `npm run dev` in a plain browser and for
 * the UI tests. It has a pretend plotter (an AxiDraw SE/A1 named "Demo" until `model` is changed), paper and
 * a Jobs list. It doesn't plot; Plan 2b-2 extends it for that.
 */
import { pieceBox } from "../geometry/placement";
import { normalizeAngle, type Units } from "../geometry/units";
import type {
  Api,
  Failure,
  JobInfo,
  MachineStatus,
  Material,
  ModelInfo,
  PaperChoice,
  PaperInfo,
  PenTypeInfo,
  PieceInfo,
  PlotStatus,
} from "./contract";

export const FAKE_MODELS: ModelInfo[] = [
  { number: 1, name: "AxiDraw V2 / V3 / SE/A4", travel: [299.974, 217.932] },
  { number: 2, name: "AxiDraw V3/A3 or SE/A3", travel: [430.022, 296.926] },
  { number: 3, name: "AxiDraw V3 XLX", travel: [594.868, 217.932] },
  { number: 4, name: "AxiDraw MiniKit", travel: [160.02, 101.6] },
  { number: 5, name: "AxiDraw SE/A1", travel: [864.108, 594.106] },
  { number: 6, name: "AxiDraw SE/A2", travel: [594.106, 432.054] },
  { number: 7, name: "AxiDraw V3/B6", travel: [189.992, 139.954] },
];

const PAPERS: PaperInfo[] = [
  { key: "letter", label: "Letter", short_mm: 215.9, long_mm: 279.4 },
  { key: "legal", label: "Legal", short_mm: 215.9, long_mm: 355.6 },
  { key: "tabloid", label: "Tabloid 11×17", short_mm: 279.4, long_mm: 431.8 },
  { key: "a4", label: "A4", short_mm: 210, long_mm: 297 },
  { key: "a3", label: "A3", short_mm: 297, long_mm: 420 },
  { key: "a2", label: "A2", short_mm: 420, long_mm: 594 },
  { key: "a1", label: "A1", short_mm: 594, long_mm: 841 },
];

const PEN_TYPES: PenTypeInfo[] = [
  { key: "fineliner", label: "Fine liner", speed: 25 },
  { key: "marker", label: "Marker", speed: 35 },
  { key: "brush", label: "Brush / paint pen", speed: 12 },
];

const IDLE: PlotStatus = { state: "idle", actions: [], layer: 0, layers: 0, color: null, name: null, message: "", details: "" };
const PEN_DOWN_MAX = 80;
const NOT_CONNECTED = "No plotter is connected. Plug in the USB cable and the power adapter.";
const NEEDS_MODEL = "Choose which AxiDraw this is first.";
const NOT_HOMED = "Slide the pen to the corner next to the HOME label and the USB port, then click It's in the corner.";
const NO_POWER = "The power adapter isn't plugged in. The pen can't move without it.";
const AFFINITY = "Affinity files can't be opened directly. In Affinity, use File › Export › SVG or PDF, then import that file.";

function ok<T extends object>(data: T): { ok: true } & T {
  return { ok: true, ...data };
}

function fail(message: string, details = ""): Failure {
  return { ok: false, message, details };
}

function demoJob(id: string, name: string, path: string, page: number): JobInfo {
  return {
    id,
    name,
    path,
    page,
    width_mm: 120,
    height_mm: 80,
    issues: [],
    groups: [
      { color: "#000000", name: "black", white: false, lines: [[0, 0, 120, 0, 120, 80, 0, 80, 0, 0], [20, 20, 100, 20]] },
      { color: "#ff0000", name: "red", white: false, lines: [[0, 80, 120, 0]] },
    ],
    preview: null,
  };
}

export class FakeApi implements Api {
  /** Test knobs: whether the pretend plotter is plugged in and powered, and its stored model (null: unknown). */
  plugged = true;
  powered = true;
  model: number | null = 5;
  /** Every call in order, as [method, args]. */
  readonly calls: [string, unknown[]][] = [];

  private connected = false;
  private homed = false;
  private position: [number, number] = [0, 0];
  private penDown = 30;
  private penType = "fineliner";
  private units: Units = "in";
  private paper: PaperChoice = { size: "letter", orientation: "landscape", custom_width_mm: null, custom_height_mm: null };
  private material = { x: 0, y: 0, width: 279.4, height: 215.9 };
  private margin = 6.35;
  private jobs: JobInfo[] = [];
  private pieces: PieceInfo[] = [];
  private readonly hidden = new Set<string>();
  private nextJob = 1;
  private nextPiece = 1;

  /** The arguments of every call to `method`. */
  called(method: string): unknown[][] {
    return this.calls.filter(([name]) => name === method).map(([, args]) => args);
  }

  private log(method: string, args: unknown[]): void {
    this.calls.push([method, args]);
  }

  private modelInfo(): ModelInfo | undefined {
    return this.connected ? FAKE_MODELS.find((m) => m.number === this.model) : undefined;
  }

  private status(): MachineStatus {
    const model = this.modelInfo();
    const state = !this.connected ? "no_plotter" : this.model === null ? "needs_model" : this.homed ? "ready" : "not_homed";
    return {
      state,
      firmware: this.connected ? "EBBv13_and_above EB Firmware Version 2.8.1" : "",
      power_ok: this.connected && this.powered,
      model: model ? model.number : null,
      model_name: model ? model.name : null,
      penlift: model ? 1 : null,
      label: model ? "Demo" : null,
      nickname: model ? `Demo m${model.number}p1` : null,
      old_firmware: false,
      position: state === "ready" ? [this.position[0], this.position[1]] : null,
      pen_down: this.penDown,
      pen_type: this.penType,
    };
  }

  private materialInfo(): Material {
    const model = this.modelInfo();
    const reach: [number, number] | null = model ? [model.travel[0], model.travel[1]] : null;
    const m = this.material;
    const fits = reach ? m.x + m.width <= reach[0] + 0.08 && m.y + m.height <= reach[1] + 0.08 : null;
    return { ...m, reach, fits };
  }

  private problem(needHome: boolean): Failure | null {
    if (!this.connected) return fail(NOT_CONNECTED);
    if (this.model === null) return fail(NEEDS_MODEL);
    if (needHome && !this.homed) return fail(NOT_HOMED);
    if (!this.powered) return fail(NO_POWER);
    return null;
  }

  private moveTo(x: number, y: number) {
    const travel = this.modelInfo()?.travel ?? [0, 0];
    this.position = [Math.min(Math.max(x, 0), travel[0] - 1), Math.min(Math.max(y, 0), travel[1] - 1)];
    return ok({ machine: this.status() });
  }

  async app_start() {
    this.log("app_start", []);
    return ok({
      version: "0.1.0 (demo)",
      settings: { units: this.units, margin_mm: this.margin, paper: { ...this.paper }, advanced: {} },
      models: FAKE_MODELS.map((m) => ({ ...m, travel: [m.travel[0], m.travel[1]] as [number, number] })),
      pen_types: PEN_TYPES,
      papers: PAPERS,
      advanced_options: { labels: {}, ranges: {}, choices: {} },
      pen_down_max: PEN_DOWN_MAX,
      machine: this.status(),
      material: this.materialInfo(),
      plot: { ...IDLE },
    });
  }

  async set_units(units: Units) {
    this.log("set_units", [units]);
    this.units = units;
    return ok({});
  }

  async diagnostics() {
    this.log("diagnostics", []);
    return ok({ text: "Rosetta Plotter (demo backend)\nNo real plotter is connected." });
  }

  async quit_confirmed() {
    this.log("quit_confirmed", []);
    return ok({});
  }

  async plotter_scan() {
    this.log("plotter_scan", []);
    this.connected = this.plugged;
    if (!this.plugged) this.homed = false;
    return ok({ machine: this.status() });
  }

  async plotter_identify(model: number, penlift: number, label: string) {
    this.log("plotter_identify", [model, penlift, label]);
    if (!this.connected) return fail(NOT_CONNECTED);
    this.model = model;
    return ok({ machine: this.status() });
  }

  async plotter_motors_off() {
    this.log("plotter_motors_off", []);
    if (!this.connected) return fail(NOT_CONNECTED);
    if (this.model === null) return fail(NEEDS_MODEL);
    this.homed = false;
    return ok({ machine: this.status() });
  }

  async plotter_set_home() {
    this.log("plotter_set_home", []);
    const problem = this.problem(false);
    if (problem) return problem;
    this.homed = true;
    this.position = [0, 0];
    return ok({ machine: this.status() });
  }

  async plotter_jog(dx: number, dy: number) {
    this.log("plotter_jog", [dx, dy]);
    return this.problem(true) ?? this.moveTo(this.position[0] + dx, this.position[1] + dy);
  }

  async plotter_goto(x: number, y: number) {
    this.log("plotter_goto", [x, y]);
    return this.problem(true) ?? this.moveTo(x, y);
  }

  async plotter_pen(down: boolean) {
    this.log("plotter_pen", [down]);
    return this.problem(true) ?? ok({ machine: this.status() });
  }

  async plotter_stop() {
    this.log("plotter_stop", []);
    return ok({});
  }

  async plotter_test_mark() {
    this.log("plotter_test_mark", []);
    const problem = this.problem(true);
    if (problem) return problem;
    this.position = [0, 0];
    return ok({ machine: this.status() });
  }

  async pen_set(penDown: number, penType: string) {
    this.log("pen_set", [penDown, penType]);
    if (!Number.isInteger(penDown) || penDown < 0 || penDown > PEN_DOWN_MAX) {
      return fail("Something unexpected went wrong.", "ValueError: pen-down height");
    }
    this.penDown = penDown;
    this.penType = penType;
    return ok({ machine: this.status() });
  }

  async material_set(size: string, orientation: string, customWidth: number | null, customHeight: number | null, x: number, y: number) {
    this.log("material_set", [size, orientation, customWidth, customHeight, x, y]);
    let width: number;
    let height: number;
    if (size === "custom") {
      const usable = (v: number | null) => v !== null && Number.isFinite(v) && v > 0 && v <= 2000;
      if (!usable(customWidth) || !usable(customHeight)) return fail("Paper width and height must be between 0 and 2000 mm.");
      width = customWidth as number;
      height = customHeight as number;
    } else {
      const paper = PAPERS.find((p) => p.key === size);
      if (!paper) return fail("Something unexpected went wrong.", `ValueError: Unknown paper size: ${size}`);
      [width, height] = orientation === "landscape" ? [paper.long_mm, paper.short_mm] : [paper.short_mm, paper.long_mm];
    }
    if (x < 0 || y < 0) return fail("Place the paper's corner at the Home corner or farther from it.");
    this.material = { x, y, width, height };
    this.paper = {
      size,
      orientation: orientation === "portrait" ? "portrait" : "landscape",
      custom_width_mm: size === "custom" ? width : null,
      custom_height_mm: size === "custom" ? height : null,
    };
    return ok({ material: this.materialInfo() });
  }

  async material_mark_corner() {
    this.log("material_mark_corner", []);
    if (!this.connected || !this.homed) return fail(NOT_HOMED);
    this.material = { ...this.material, x: this.position[0], y: this.position[1] };
    return ok({ material: this.materialInfo() });
  }

  async set_margin(margin: number) {
    this.log("set_margin", [margin]);
    if (!(margin >= 0 && margin <= 50)) return fail("The margin must be from 0 to 50 mm.");
    this.margin = margin;
    return ok({ margin_mm: margin });
  }

  async artwork_choose() {
    this.log("artwork_choose", []);
    return ok({ paths: ["C:\\Demo\\site-plan.svg"] });
  }

  async artwork_pages(path: string) {
    this.log("artwork_pages", [path]);
    return ok({ pages: path.toLowerCase().endsWith(".pdf") ? 3 : 1 });
  }

  async job_import(path: string, page: number) {
    this.log("job_import", [path, page]);
    if (/\.(afdesign|afphoto|afpub|af)$/i.test(path)) return fail(AFFINITY);
    const file = path.split(/[\\/]/).pop() ?? path;
    const stem = file.replace(/\.[^.]+$/, "");
    const name = path.toLowerCase().endsWith(".pdf") ? `${stem} (page ${page + 1})` : stem;
    const job = demoJob(`job-${this.nextJob++}`, name, path, page);
    this.jobs.push(job);
    return ok({ job });
  }

  async job_list() {
    this.log("job_list", []);
    return ok({ jobs: [...this.jobs], pieces: this.pieces.map((p) => ({ ...p, placement: { ...p.placement } })) });
  }

  async job_place(jobId: string, x: number, y: number) {
    this.log("job_place", [jobId, x, y]);
    if (!this.jobs.some((j) => j.id === jobId)) return fail("That file isn't in the Jobs list anymore.");
    const piece: PieceInfo = { id: `piece-${this.nextPiece++}`, job_id: jobId, placement: { x, y, scale: 1, scale_y: 1, rotation: 0 } };
    this.pieces.push(piece);
    return ok({ piece: { ...piece, placement: { ...piece.placement } } });
  }

  async job_remove(jobId: string) {
    this.log("job_remove", [jobId]);
    if (!this.jobs.some((j) => j.id === jobId)) return fail("That file isn't in the Jobs list anymore.");
    const removed = this.pieces.filter((p) => p.job_id === jobId).map((p) => p.id);
    this.pieces = this.pieces.filter((p) => p.job_id !== jobId);
    this.jobs = this.jobs.filter((j) => j.id !== jobId);
    return ok({ removed_pieces: removed });
  }

  async piece_place(pieceId: string, x: number, y: number, scale: number, rotation: number, scaleY: number) {
    this.log("piece_place", [pieceId, x, y, scale, rotation, scaleY]);
    const piece = this.pieces.find((p) => p.id === pieceId);
    if (!piece) return fail("That drawing isn't on the paper anymore.");
    const usable = [x, y, scale, rotation, scaleY].every(Number.isFinite) && scale > 0 && scaleY > 0;
    if (!usable) return fail("Something unexpected went wrong.", "ValueError: placement");
    piece.placement = { x, y, scale, scale_y: scaleY, rotation: normalizeAngle(rotation) };
    return ok({ placement: { ...piece.placement } });
  }

  async piece_duplicate(pieceId: string) {
    this.log("piece_duplicate", [pieceId]);
    const index = this.pieces.findIndex((p) => p.id === pieceId);
    if (index < 0) return fail("That drawing isn't on the paper anymore.");
    const original = this.pieces[index];
    const copy: PieceInfo = {
      id: `piece-${this.nextPiece++}`,
      job_id: original.job_id,
      placement: { ...original.placement, x: original.placement.x + 10, y: original.placement.y + 10 },
    };
    this.pieces.splice(index + 1, 0, copy);
    return ok({ piece: { ...copy, placement: { ...copy.placement } } });
  }

  async piece_delete(pieceId: string) {
    this.log("piece_delete", [pieceId]);
    this.pieces = this.pieces.filter((p) => p.id !== pieceId);
    return ok({});
  }

  async paper_rotate() {
    this.log("paper_rotate", []);
    const oldHeight = this.material.height;
    this.material = { ...this.material, width: this.material.height, height: this.material.width };
    for (const piece of this.pieces) {
      const job = this.jobs.find((j) => j.id === piece.job_id);
      if (!job) continue;
      const box = pieceBox(job.width_mm, job.height_mm, piece.placement);
      piece.placement = {
        ...piece.placement,
        x: oldHeight - piece.placement.y - box.height,
        y: piece.placement.x,
        rotation: normalizeAngle(piece.placement.rotation + 90),
      };
    }
    if (this.paper.size === "custom") {
      this.paper = { ...this.paper, custom_width_mm: this.material.width, custom_height_mm: this.material.height };
    } else {
      this.paper = { ...this.paper, orientation: this.paper.orientation === "landscape" ? "portrait" : "landscape" };
    }
    return ok({
      material: this.materialInfo(),
      paper: { ...this.paper },
      pieces: this.pieces.map((p) => ({ ...p, placement: { ...p.placement } })),
    });
  }

  async set_pen_visible(color: string, visible: boolean) {
    this.log("set_pen_visible", [color, visible]);
    if (visible) this.hidden.delete(color.toLowerCase());
    else this.hidden.add(color.toLowerCase());
    return ok({ hidden: [...this.hidden].sort() });
  }

  async job_colors() {
    this.log("job_colors", []);
    const seen: { color: string; name: string; lines: number }[] = [];
    for (const piece of this.pieces) {
      const job = this.jobs.find((j) => j.id === piece.job_id);
      for (const group of job?.groups ?? []) {
        if (group.white) continue;
        const known = seen.find((c) => c.color === group.color);
        if (known) known.lines += group.lines.length;
        else seen.push({ color: group.color, name: group.name, lines: group.lines.length });
      }
    }
    let layer = 0;
    const colors = seen.map((c) => {
      const visible = !this.hidden.has(c.color);
      if (visible) layer += 1;
      return { ...c, layer: visible ? layer : null, visible };
    });
    return ok({ colors, ink_bbox: null, clipped: false, empty: colors.length === 0 });
  }

  async plot_status() {
    this.log("plot_status", []);
    return ok({ plot: { ...IDLE }, machine: this.status() });
  }
}
