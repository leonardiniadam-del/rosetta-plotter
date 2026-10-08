/** The bridge to Python (docs/bridge.md): the methods and replies this page uses. Lengths are mm. */
import type { Units } from "../geometry/units";

export type Failure = { ok: false; message: string; details: string };
export type Reply<T> = Promise<({ ok: true } & T) | Failure>;

export type MachineState = "no_plotter" | "needs_model" | "not_homed" | "ready" | "plotting";

export interface MachineStatus {
  state: MachineState;
  firmware: string;
  power_ok: boolean;
  model: number | null;
  model_name: string | null;
  penlift: number | null;
  label: string | null;
  nickname: string | null;
  old_firmware: boolean;
  position: [number, number] | null;
  pen_down: number;
  pen_type: string;
}

export interface Material {
  x: number;
  y: number;
  width: number;
  height: number;
  reach: [number, number] | null;
  fits: boolean | null;
}

export interface PaperChoice {
  size: string;
  orientation: "landscape" | "portrait";
  custom_width_mm: number | null;
  custom_height_mm: number | null;
}

export interface Issue {
  code: string;
  message: string;
  count: number;
}

export interface ColorLines {
  color: string;
  name: string;
  white: boolean;
  lines: number[][];
}

export interface JobInfo {
  id: string;
  name: string;
  path: string;
  page: number;
  width_mm: number;
  height_mm: number;
  issues: Issue[];
  groups: ColorLines[];
  preview: string | null;
}

export interface PlacementData {
  x: number;
  y: number;
  scale: number;
  scale_y: number;
  rotation: number;
}

export interface PieceInfo {
  id: string;
  job_id: string;
  placement: PlacementData;
}

export interface PenColor {
  layer: number | null;
  color: string;
  name: string;
  lines: number;
  visible: boolean;
}

export interface ColorsSummary {
  colors: PenColor[];
  ink_bbox: number[] | null;
  clipped: boolean;
  empty: boolean;
}

export interface PlotStatus {
  state: string;
  actions: string[];
  layer: number;
  layers: number;
  color: string | null;
  name: string | null;
  message: string;
  details: string;
}

/** Advanced options by name (bridge.md set_advanced): null means automatic for pen_up and speed_pendown. */
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

export interface ModelInfo {
  number: number;
  name: string;
  travel: [number, number];
}

export interface PenTypeInfo {
  key: string;
  label: string;
  speed: number;
}

export interface PaperInfo {
  key: string;
  label: string;
  short_mm: number;
  long_mm: number;
}

export interface AppStart {
  version: string;
  settings: { units: Units; margin_mm: number; paper: PaperChoice; advanced: AdvancedValues };
  models: ModelInfo[];
  pen_types: PenTypeInfo[];
  papers: PaperInfo[];
  advanced_options: {
    labels: Record<string, string>;
    ranges: Record<string, [number, number]>;
    choices: Record<string, number[]>;
    defaults: AdvancedValues;
  };
  pen_down_max: number;
  machine: MachineStatus;
  material: Material;
  plot: PlotStatus;
}

type MachineReply = Reply<{ machine: MachineStatus }>;
type PlotReply = Reply<{ plot: PlotStatus; machine: MachineStatus }>;

export interface Api {
  app_start(): Reply<AppStart>;
  set_units(units: Units): Reply<object>;
  set_advanced(values: AdvancedValues): Reply<{ advanced: AdvancedValues }>;
  diagnostics(): Reply<{ text: string }>;
  quit_confirmed(): Reply<object>;
  plotter_scan(): MachineReply;
  plotter_identify(model: number, penlift: number, label: string): MachineReply;
  plotter_motors_off(): MachineReply;
  plotter_set_home(): MachineReply;
  plotter_jog(dx: number, dy: number): MachineReply;
  plotter_goto(x: number, y: number): MachineReply;
  plotter_pen(down: boolean): MachineReply;
  plotter_stop(): Reply<object>;
  plotter_test_mark(): MachineReply;
  pen_set(pen_down: number, pen_type: string): MachineReply;
  material_set(
    size: string,
    orientation: string,
    custom_width_mm: number | null,
    custom_height_mm: number | null,
    x: number,
    y: number,
  ): Reply<{ material: Material }>;
  material_mark_corner(): Reply<{ material: Material }>;
  set_margin(margin_mm: number): Reply<{ margin_mm: number }>;
  artwork_choose(): Reply<{ paths: string[] }>;
  artwork_pages(path: string): Reply<{ pages: number }>;
  job_import(path: string, page: number): Reply<{ job: JobInfo }>;
  job_list(): Reply<{ jobs: JobInfo[]; pieces: PieceInfo[] }>;
  job_place(job_id: string, x: number, y: number): Reply<{ piece: PieceInfo }>;
  job_remove(job_id: string): Reply<{ removed_pieces: string[] }>;
  piece_place(
    piece_id: string,
    x: number,
    y: number,
    scale: number,
    rotation: number,
    scale_y: number,
  ): Reply<{ placement: PlacementData }>;
  piece_duplicate(piece_id: string): Reply<{ piece: PieceInfo }>;
  piece_delete(piece_id: string): Reply<object>;
  paper_rotate(): Reply<{ material: Material; paper: PaperChoice; pieces: PieceInfo[] }>;
  set_pen_visible(color: string, visible: boolean): Reply<{ hidden: string[] }>;
  set_skip_white(skip: boolean): Reply<{ skip_white: boolean }>;
  job_colors(): Reply<ColorsSummary>;
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
  plot_status(): PlotReply;
}
