/**
 * FakeApi: a stand-in for Python that follows docs/bridge.md, for `npm run dev` in a plain browser and for
 * the UI tests. It has a pretend plotter (an AxiDraw SE/A1 named "Demo" until `model` is changed), paper and
 * a Jobs list. Its pretend plot follows rosetta.app.plotjob's states, actions and messages; the knobs
 * `progress`, `finishLayer` and `disconnect` (or `autoplay` under `npm run dev`) stand in for the plot running.
 */
import { applyMatrix, MAX_SCALE, pieceBox, pieceMatrix } from "../geometry/placement";
import { isOrientation, type OrientationCode } from "../geometry/orientation";
import { normalizeAngle, type Units } from "../geometry/units";
import type {
  AdvancedValues,
  Api,
  Failure,
  JobInfo,
  MachineStatus,
  Material,
  ModelInfo,
  PaperChoice,
  PaperInfo,
  PenColor,
  PenTypeInfo,
  PieceInfo,
  PlotRun,
  PlotStatus,
  PlotSummary,
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

const PEN_DOWN_MAX = 80;
const MIN_PEN_TRAVEL = 10;
const NOT_CONNECTED = "No plotter is connected. Plug in the USB cable and the power adapter.";
const NEEDS_MODEL = "Choose which AxiDraw this is first.";
const NOT_HOMED = "Slide the pen to the corner next to the HOME label and the USB port, then click It's in the corner.";
const NO_POWER = "The power adapter isn't plugged in. The pen can't move without it.";
const BUSY = "The plotter is still busy. Wait for it to finish, then try again.";
const PLOTTING = "The plotter is in the middle of a plot. Finish or cancel the plot first.";
const STOPPED_MOVING = "The plotter stopped before the move finished. Slide the pen Home, then click It's in the corner.";
const GONE = "That drawing isn't on the paper anymore.";
export const TOO_BIG = "Drawings can be scaled up to 10000%.";
const AFFINITY ="Affinity files can't be opened directly. In Affinity, use File › Export › SVG or PDF, then import that file.";

// The pretend plot: the same states, actions and messages as rosetta.app.plotjob.
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
const NOTHING_TO_PLOT = "Nothing to plot: no lines land on the paper.";
const FINISH_FIRST = "Finish or cancel the current plot first.";
const PREPARE_FIRST = "Wait a moment: the plot is still being prepared.";
const STILL_PREPARING = "The plot is still being prepared. Wait a moment, then try again.";
const CHANGED_WHILE_PREPARING = "Something changed while the plot was being prepared, so it's being prepared again.";
const NOT_NOW = "That can't be done right now.";
const DONE = "Done! The pen is back Home.";
const HOME_UNKNOWN = "Slide the pen Home before the next plot.";
const CHECK_CABLE = "Check the USB cable and the power adapter, then click Continue.";
const PAUSED = "Paused. The pen is up.";

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
const AUTOMATIC = ["pen_up", "speed_pendown"]; // null means Rosetta decides
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

const round = (value: number, places: number): number => Number(value.toFixed(places));

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
  /** Test knob: the plotter's firmware is too old to store its model in its nickname. */
  oldFirmware = false;
  /** Every call in order, as [method, args]. */
  readonly calls: [string, unknown[]][] = [];

  private connected = false;
  private homed = false;
  /** The label kept in the plotter's nickname (null: the demo's own). */
  private labelStored: string | null = null;
  private position: [number, number] = [0, 0];
  private penDown = 30;
  private penType = "fineliner";
  private units: Units = "in";
  /** The saved plate orientation (one for every plotter: the fake has only one). */
  orientation: OrientationCode = "nw-h";
  private paper: PaperChoice = { size: "letter", orientation: "landscape", custom_width_mm: null, custom_height_mm: null };
  private material = { x: 0, y: 0, width: 279.4, height: 215.9 };
  private margin = 6.35;
  private jobs: JobInfo[] = [];
  private pieces: PieceInfo[] = [];
  private readonly hidden = new Set<string>();
  private nextJob = 1;
  private nextPiece = 1;
  private readonly holds = new Map<string, Promise<void>>();
  private readonly failures = new Map<string, string>();

  /** Events, as Python sends them through window.rosettaEvent. Tests and `npm run dev` connect it to App.onEvent. */
  emit: (name: string, data: unknown) => void = () => {};
  private plotState = "idle";
  private plotMessage = "";
  private prepared: PlotSummary | null = null;
  private layerIndex = 0;
  private preparing = false;
  /** Something changed mid-plot (or mid-prepare): the prepared plot is dropped once the plot is over. */
  private stale = false;
  /** Is the pen known to be Home during a plot? A cancel otherwise leaves the plotter to be re-homed. */
  private atHome = true;
  private pauseWanted = false;
  private stopRequested = false;
  private skipWhite = true;
  private advanced: AdvancedValues = { ...FAKE_ADVANCED };
  private autoFraction = 0;

  /** The arguments of every call to `method`. */
  called(method: string): unknown[][] {
    return this.calls.filter(([name]) => name === method).map(([, args]) => args);
  }

  private log(method: string, args: unknown[]): void {
    this.calls.push([method, args]);
  }

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

  private modelInfo(): ModelInfo | undefined {
    return this.connected ? FAKE_MODELS.find((m) => m.number === this.model) : undefined;
  }

  /** A plot has the plotter (machine.state "plotting"): from Start until it's done or cancelled, as in Python. */
  private machinePlotting(): boolean {
    return !AT_REST.includes(this.plotState) && this.plotState !== "tracing";
  }

  private status(): MachineStatus {
    const model = this.modelInfo();
    const state = !this.connected
      ? "no_plotter"
      : this.model === null
        ? "needs_model"
        : this.machinePlotting()
          ? "plotting"
          : this.homed
            ? "ready"
            : "not_homed";
    return {
      state,
      firmware: this.connected ? "EBBv13_and_above EB Firmware Version 2.8.1" : "",
      power_ok: this.connected && this.powered,
      model: model ? model.number : null,
      model_name: model ? model.name : null,
      penlift: model ? 1 : null,
      label: model ? (this.labelStored ?? "Demo") : null,
      nickname: model ? `Demo m${model.number}p1` : null,
      old_firmware: this.connected && this.oldFirmware,
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

  /** Why the plotter can't move now, as Machine._using and _check_power say it. */
  private problem(needHome: boolean): Failure | null {
    if (this.plotState === "tracing") return fail(BUSY);
    if (!this.connected) return fail(NOT_CONNECTED);
    if (this.model === null) return fail(NEEDS_MODEL);
    if (this.machinePlotting()) return fail(PLOTTING);
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
      settings: { units: this.units, margin_mm: this.margin, paper: { ...this.paper }, advanced: { ...this.advanced } },
      models: FAKE_MODELS.map((m) => ({ ...m, travel: [m.travel[0], m.travel[1]] as [number, number] })),
      pen_types: PEN_TYPES,
      papers: PAPERS,
      advanced_options: { labels: ADVANCED_LABELS, ranges: ADVANCED_RANGES, choices: ADVANCED_CHOICES, defaults: { ...FAKE_ADVANCED } },
      pen_down_max: PEN_DOWN_MAX,
      machine: this.status(),
      material: this.materialInfo(),
      plot: this.plotInfo(),
      orientation: this.orientation,
    });
  }

  async set_orientation(code: OrientationCode) {
    this.log("set_orientation", [code]);
    if (!isOrientation(code)) return fail(`Unknown orientation: ${String(code)}`);
    this.orientation = code;
    return ok({ orientation: code });
  }

  async set_units(units: Units) {
    this.log("set_units", [units]);
    this.units = units;
    return ok({});
  }

  async set_advanced(values: AdvancedValues) {
    this.log("set_advanced", [values]);
    for (const [name, value] of Object.entries(values)) {
      const label = ADVANCED_LABELS[name];
      if (!label) return fail(`Unknown advanced option: ${name}`);
      if (name === "hiding") {
        if (typeof value !== "boolean") return fail(`${label} must be on or off.`);
        continue;
      }
      if (value === null && AUTOMATIC.includes(name)) continue;
      if (typeof value !== "number" || !Number.isInteger(value)) return fail(`${label} must be a whole number.`);
      const choices = ADVANCED_CHOICES[name];
      if (choices && !choices.includes(value)) return fail(`${label} must be one of ${choices.join(", ")}.`);
      const range = ADVANCED_RANGES[name];
      if (range && !(value >= range[0] && value <= range[1])) return fail(`${label} must be from ${range[0]} to ${range[1]}.`);
    }
    const advanced = { ...this.advanced, ...values };
    const penUp = advanced.pen_up;
    if ("pen_up" in values && typeof penUp === "number" && penUp - this.penDown < MIN_PEN_TRAVEL) {
      return fail(`Pen-up height must be at least ${MIN_PEN_TRAVEL} above the pen-down height (${this.penDown}).`);
    }
    this.advanced = advanced;
    this.invalidate();
    return ok({ advanced: { ...this.advanced } });
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
    if (this.machinePlotting()) return ok({ machine: this.status(), orientation: this.orientation }); // the plot has the plotter
    this.connected = this.plugged;
    if (!this.plugged) this.homed = false;
    return ok({ machine: this.status(), orientation: this.orientation });
  }

  async plotter_identify(model: number, penlift: number, label: string) {
    this.log("plotter_identify", [model, penlift, label]);
    if (!this.connected) return fail(NOT_CONNECTED);
    if (this.machinePlotting()) return fail(PLOTTING);
    this.model = model;
    this.labelStored = label.slice(0, 16); // a stand-in for the plotter's shorter limit
    this.invalidate();
    return ok({ machine: this.status(), orientation: this.orientation });
  }

  async plotter_motors_off() {
    this.log("plotter_motors_off", []);
    if (!this.connected) return fail(NOT_CONNECTED);
    if (this.model === null) return fail(NEEDS_MODEL);
    if (this.machinePlotting()) return fail(PLOTTING);
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
    return this.problem(false) ?? ok({ machine: this.status() });
  }

  async plotter_stop() {
    this.log("plotter_stop", []);
    this.stopRequested = true;
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
    const penUp = this.advanced.pen_up;
    if (typeof penUp === "number" && penUp - penDown < MIN_PEN_TRAVEL) {
      return fail(`The pen-up height under Advanced (${penUp}) must be at least ${MIN_PEN_TRAVEL} above the pen-down height.`);
    }
    this.penDown = penDown;
    this.penType = penType;
    this.invalidate(); // during a plot: remembered for the next one
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
    this.invalidate();
    return ok({ material: this.materialInfo() });
  }

  async material_mark_corner() {
    this.log("material_mark_corner", []);
    if (!this.connected || !this.homed || this.machinePlotting()) return fail(NOT_HOMED);
    this.material = { ...this.material, x: this.position[0], y: this.position[1] };
    this.invalidate();
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
    this.invalidate();
    return ok({ piece: { ...piece, placement: { ...piece.placement } } });
  }

  async job_remove(jobId: string) {
    this.log("job_remove", [jobId]);
    if (!this.jobs.some((j) => j.id === jobId)) return fail("That file isn't in the Jobs list anymore.");
    const removed = this.pieces.filter((p) => p.job_id === jobId).map((p) => p.id);
    this.pieces = this.pieces.filter((p) => p.job_id !== jobId);
    this.jobs = this.jobs.filter((j) => j.id !== jobId);
    this.invalidate();
    return ok({ removed_pieces: removed });
  }

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
    this.invalidate();
    return ok({ placement: { ...piece.placement } });
  }

  async piece_duplicate(pieceId: string) {
    this.log("piece_duplicate", [pieceId]);
    const index = this.pieces.findIndex((p) => p.id === pieceId);
    if (index < 0) return fail(GONE);
    const original = this.pieces[index];
    const copy: PieceInfo = {
      id: `piece-${this.nextPiece++}`,
      job_id: original.job_id,
      placement: { ...original.placement, x: original.placement.x + 10, y: original.placement.y + 10 },
    };
    this.pieces.splice(index + 1, 0, copy);
    this.invalidate();
    return ok({ piece: { ...copy, placement: { ...copy.placement } } });
  }

  async piece_delete(pieceId: string) {
    this.log("piece_delete", [pieceId]);
    if (!this.pieces.some((p) => p.id === pieceId)) return fail(GONE);
    this.pieces = this.pieces.filter((p) => p.id !== pieceId);
    this.invalidate();
    return ok({});
  }

  async paper_rotate() {
    this.log("paper_rotate", []);
    if (!AT_REST.includes(this.plotState)) return fail(FINISH_FIRST);
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
    const flipped = this.paper.orientation === "landscape" ? "portrait" : "landscape";
    const custom = this.paper.size === "custom";
    this.paper = {
      ...this.paper,
      orientation: flipped,
      custom_width_mm: custom ? this.material.width : null,
      custom_height_mm: custom ? this.material.height : null,
    };
    this.invalidate();
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
    this.invalidate();
    return ok({ hidden: [...this.hidden].sort() });
  }

  async set_skip_white(skip: boolean) {
    this.log("set_skip_white", [skip]);
    this.skipWhite = skip;
    this.invalidate();
    return ok({ skip_white: skip });
  }

  async job_colors() {
    this.log("job_colors", []);
    const colors = this.colorList();
    return ok({ colors, ink_bbox: null, clipped: false, empty: colors.length === 0 });
  }

  /** Every pen color the placed drawings use, in plot order; hidden ones have no layer. */
  private colorList(): PenColor[] {
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
    return seen.map((c) => {
      const visible = !this.hidden.has(c.color);
      if (visible) layer += 1;
      return { ...c, layer: visible ? layer : null, visible };
    });
  }

  // The plot (bridge.md "Plot"), following rosetta.app.plotjob.PlotController.

  async plot_prepare() {
    this.log("plot_prepare", []);
    if (this.preparing) return fail(STILL_PREPARING);
    if (!AT_REST.includes(this.plotState)) return fail(FINISH_FIRST);
    this.preparing = true;
    this.stale = false;
    const refused = await this.gate("plot_prepare"); // hold() stands in for a slow plan
    this.preparing = false;
    if (refused) return refused;
    if (!this.connected || this.model === null) return fail(NOT_CONNECTED); // Machine.plot_settings
    const summary = this.summary();
    if (summary.layers.length === 0) return fail(NOTHING_TO_PLOT);
    if (this.stale) {
      this.stale = false;
      this.setPlot("idle"); // tells the page to prepare the plot again
      return fail(CHANGED_WHILE_PREPARING);
    }
    this.prepared = summary;
    this.layerIndex = 0;
    this.setPlot("ready");
    return ok({ summary });
  }

  async plot_trace() {
    this.log("plot_trace", []);
    const unprepared = this.needPrepared();
    if (unprepared) return unprepared;
    const problem = this.problem(true);
    this.setPlot("tracing");
    this.stopRequested = false;
    let reply: Failure | { ok: true; machine: MachineStatus };
    const refused = problem ?? (await this.gate("plot_trace")); // hold() stands in for the pen going around
    if (refused) {
      reply = refused;
    } else if (this.stopRequested) {
      this.homed = false; // stopped partway: the pen's position is unknown
      reply = fail(STOPPED_MOVING);
    } else {
      this.position = [0, 0];
      reply = ok({ machine: this.status() });
    }
    this.rest("ready");
    return reply;
  }

  async plot_start() {
    this.log("plot_start", []);
    const refused = (await this.gate("plot_start")) ?? this.needPrepared() ?? this.problem(true);
    if (refused) return refused;
    this.layerIndex = 0;
    this.position = [0, 0];
    this.atHome = true;
    if ((this.prepared?.layers.length ?? 0) > 1) this.askForPen();
    else this.runLayer();
    return this.plotReply();
  }

  async plot_continue() {
    this.log("plot_continue", []);
    const refused = this.expect("load_pen") ?? this.powerProblem();
    if (refused) return refused;
    this.runLayer();
    return this.plotReply();
  }

  async plot_pause() {
    this.log("plot_pause", []);
    if (this.plotState === "plotting") {
      this.setPlot("pausing", "Pausing...");
      setTimeout(() => {
        if (this.plotState === "pausing") this.setPlot("paused", PAUSED);
      }, 0);
    } else if (this.plotState === "homing") {
      this.pauseWanted = true; // stays "homing" until the move stops, as in Python
    }
    return this.plotReply();
  }

  async plot_resume() {
    this.log("plot_resume", []);
    const refused = this.expect("paused", "paused_at_home") ?? this.powerProblem();
    if (refused) return refused;
    this.runLayer();
    return this.plotReply();
  }

  async plot_home() {
    this.log("plot_home", []);
    const refused = this.expect("paused") ?? this.powerProblem();
    if (refused) return refused;
    this.atHome = false;
    this.pauseWanted = false;
    this.setPlot("homing", "Sending the pen Home.");
    setTimeout(() => {
      if (this.plotState !== "homing") return;
      if (this.pauseWanted) {
        this.setPlot("paused", PAUSED);
        return;
      }
      this.atHome = true;
      this.setPlot("paused_at_home", "The pen is Home. Check or swap it, then click Resume.");
    }, 0);
    return this.plotReply();
  }

  async plot_cancel() {
    this.log("plot_cancel", []);
    const refused = this.expect("load_pen", "paused", "paused_at_home", "reconnect", "slide_home", "not_connected");
    if (refused) return refused;
    this.endPlot("Plot cancelled.");
    return this.plotReply();
  }

  async plot_reconnect() {
    this.log("plot_reconnect", []);
    const refused = this.expect("reconnect");
    if (refused) return refused;
    if (this.plugged) this.setPlot("slide_home", NOT_HOMED);
    else this.setPlot("reconnect", `Still no plotter found. ${CHECK_CABLE}`);
    return this.plotReply();
  }

  async plot_rehomed() {
    this.log("plot_rehomed", []);
    const refused = this.expect("slide_home");
    if (refused) return refused;
    this.atHome = true;
    this.setPlot("paused_at_home", "The pen is Home. Click Resume to carry on.");
    return this.plotReply();
  }

  async plot_retry() {
    this.log("plot_retry", []);
    const refused = this.expect("not_connected") ?? this.powerProblem();
    if (refused) return refused;
    this.runLayer();
    return this.plotReply();
  }

  async plot_status() {
    this.log("plot_status", []);
    return this.plotReply();
  }

  /** Test and demo knob: progress through the current pen (0–1), as Python's plot_progress event reports it. */
  progress(fraction: number): void {
    const layers = this.prepared?.layers ?? [];
    const layer = layers[this.layerIndex];
    if (!layer || (this.plotState !== "plotting" && this.plotState !== "pausing")) return;
    const down = layer.path.filter((run) => run.down).flatMap((run) => run.points);
    const count = Math.floor(down.length / 3);
    const index = Math.min(count - 1, Math.max(0, Math.floor(fraction * (count - 1))));
    const later = layers.slice(this.layerIndex + 1).reduce((sum, l) => sum + l.seconds, 0);
    this.emit("plot_progress", {
      layer: this.layerIndex,
      x: down[index * 3] ?? 0,
      y: down[index * 3 + 1] ?? 0,
      pendown_mm: round(layer.pendown_mm * fraction, 1),
      fraction: round(fraction, 4),
      seconds_left: round(layer.seconds * (1 - fraction) + later, 1),
    });
  }

  /** Test and demo knob: the current pen finishes, back at Home. The next one is asked for, or the plot is done. */
  finishLayer(): void {
    if (this.plotState !== "plotting" && this.plotState !== "pausing") return;
    this.atHome = true;
    this.layerIndex += 1;
    if (this.layerIndex < (this.prepared?.layers.length ?? 0)) {
      this.askForPen();
    } else {
      this.homed = true;
      this.position = [0, 0];
      this.layerIndex = 0;
      this.rest("done", DONE);
    }
  }

  /** Test and demo knob: the USB cable is pulled mid-plot. */
  disconnect(): void {
    if (["plotting", "pausing", "homing"].includes(this.plotState)) {
      this.setPlot("reconnect", "Plotter disconnected. Plug it back in, then click Continue.");
    }
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

  /** The drawing, paper, pen or plotter changed: the prepared plot is out of date (PlotController.invalidate). */
  private invalidate(): void {
    if (this.preparing || !AT_REST.includes(this.plotState)) this.stale = true;
    if (!AT_REST.includes(this.plotState)) return;
    this.prepared = null;
    this.layerIndex = 0;
    if (this.plotState !== "idle") this.setPlot("idle");
  }

  /** A plot or trace ended: at rest again, or idle (keeping the message) if something changed meanwhile. */
  private rest(state: string, message = ""): void {
    if (this.stale) {
      this.stale = false;
      this.prepared = null;
      this.layerIndex = 0;
      this.setPlot("idle", message);
    } else {
      this.setPlot(state, message);
    }
  }

  /** Give the plotter back: re-homed if the pen isn't known to be Home. The prepared plot stays for a new start. */
  private endPlot(message: string): void {
    if (this.atHome) {
      this.position = [0, 0];
    } else {
      this.homed = false;
      message = `${message} ${HOME_UNKNOWN}`;
    }
    this.layerIndex = 0;
    this.rest("ready", message);
  }

  private plotReply() {
    return ok({ plot: this.plotInfo(), machine: this.status() });
  }

  private expect(...states: string[]): Failure | null {
    return states.includes(this.plotState) ? null : fail(NOT_NOW);
  }

  private needPrepared(): Failure | null {
    if (this.preparing) return fail(STILL_PREPARING);
    if (!["ready", "done"].includes(this.plotState) || !this.prepared) {
      return fail(AT_REST.includes(this.plotState) ? PREPARE_FIRST : FINISH_FIRST);
    }
    return null;
  }

  /** Checked before every run, as Python does (spec §10). */
  private powerProblem(): Failure | null {
    return this.powered ? null : fail(NO_POWER);
  }

  /** The planned plot: per visible pen, pen up to each line and down along it, then Home. */
  private summary(): PlotSummary {
    const origin: [number, number] = [this.material.x, this.material.y];
    const ink = [Infinity, Infinity, -Infinity, -Infinity];
    const layers = this.colorList()
      .filter((c) => c.visible)
      .map((c) => {
        const runs: PlotRun[] = [];
        let at: [number, number] = [0, 0];
        let t = 0;
        let pendown = 0;
        const go = (down: boolean, points: [number, number][]) => {
          const flat = [round(at[0], 2), round(at[1], 2), round(t, 3)];
          for (const p of points) {
            const d = Math.hypot(p[0] - at[0], p[1] - at[1]);
            t += d / (down ? PEN_MM_S : TRAVEL_MM_S);
            if (down) pendown += d;
            at = p;
            flat.push(round(p[0], 2), round(p[1], 2), round(t, 3));
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
              for (const [x, y] of points) {
                ink[0] = Math.min(ink[0], x);
                ink[1] = Math.min(ink[1], y);
                ink[2] = Math.max(ink[2], x);
                ink[3] = Math.max(ink[3], y);
              }
              go(false, [points[0]]);
              go(true, points.slice(1));
            }
          }
        }
        go(false, [[0, 0]]);
        return { layer: c.layer ?? 0, color: c.color, name: c.name, seconds: round(t, 1), pendown_mm: round(pendown, 1), path: runs };
      });
    const total = layers.reduce((sum, layer) => sum + layer.seconds, 0);
    const inkBbox = Number.isFinite(ink[0]) ? ink.map((v) => round(v, 2)) : [0, 0, 0, 0];
    return { layers, total_seconds: round(total, 1), ink_bbox: inkBbox, warnings: [] };
  }

  private askForPen(): void {
    const layers = this.prepared?.layers ?? [];
    const name = layers[this.layerIndex].name;
    this.setPlot("load_pen", `Put the ${name} pen in the holder (${this.layerIndex + 1} of ${layers.length}), then click Continue.`);
  }

  private runLayer(): void {
    const layers = this.prepared?.layers ?? [];
    this.atHome = false;
    this.pauseWanted = false;
    this.autoFraction = 0;
    this.setPlot("plotting", `Plotting the ${layers[this.layerIndex].name} pen (${this.layerIndex + 1} of ${layers.length}).`);
  }
}
