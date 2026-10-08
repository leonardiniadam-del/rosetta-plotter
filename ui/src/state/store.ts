/** The app's one state, and how Lit components follow it. */
import type { ReactiveController, ReactiveControllerHost } from "lit";
import type {
  AdvancedValues,
  AppStart,
  JobInfo,
  MachineStatus,
  Material,
  PaperChoice,
  PenColor,
  PieceInfo,
  PlotStatus,
  PlotSummary,
} from "../bridge/contract";
import type { Units } from "../geometry/units";

export type Tool = "select" | "hand" | "zoom" | "rotate" | "pen";

export interface NoticeAction {
  label: string;
  run: () => void;
}

/** The notification strip across the top of the plate (spec §4.6). */
export interface Notice {
  kind: "info" | "warning" | "error";
  message: string;
  details?: string;
  actions?: NoticeAction[];
  /** Notices the plot puts up, which it takes down again. */
  source?: "plot";
  /** Stays until replaced (an info notice without buttons otherwise closes itself after a few seconds). */
  keep?: boolean;
}

export type Dialog =
  | { kind: "pages"; name: string; pages: number; resolve: (page: number | null) => void }
  | { kind: "model" }
  | { kind: "text"; title: string; text: string }
  | { kind: "shortcuts" }
  | { kind: "about" }
  | { kind: "confirm"; title: string; message: string; confirm: string; cancel: string; plot?: true; run: () => void }
  | { kind: "settings" };

export interface ViewOptions {
  grid: boolean;
  margins: boolean;
  original: boolean;
}

export interface AppState {
  ready: boolean;
  start: AppStart | null;
  units: Units;
  machine: MachineStatus;
  material: Material;
  paper: PaperChoice;
  margin: number;
  jobs: JobInfo[];
  pieces: PieceInfo[];
  colors: PenColor[];
  selection: string[];
  tool: Tool;
  /** Set Home's first click switched the motors off; the next click confirms. */
  homing: boolean;
  jogStep: 1 | 10;
  /** The W/H and W%/H% link in the control bar. */
  linkScale: boolean;
  view: ViewOptions;
  notice: Notice | null;
  dialog: Dialog | null;
  plot: PlotStatus;
  /** The prepared plot: per-pen times and the planned path (null until plot_prepare replies). */
  summary: PlotSummary | null;
  preparing: boolean;
  /** Why the plot couldn't be prepared (shown on Start), or null. */
  prepareProblem: string | null;
  skipWhite: boolean;
  advanced: AdvancedValues;
  /** Preview path: playing or paused, and the speed. Null when it isn't showing. */
  preview: { playing: boolean; speed: 1 | 4 | 16 } | null;
}

export const NO_MACHINE: MachineStatus = {
  state: "no_plotter",
  firmware: "",
  power_ok: false,
  model: null,
  model_name: null,
  penlift: null,
  label: null,
  nickname: null,
  old_firmware: false,
  position: null,
  pen_down: 30,
  pen_type: "fineliner",
};

export const IDLE_PLOT: PlotStatus = { state: "idle", actions: [], layer: 0, layers: 0, color: null, name: null, message: "", details: "" };

export function initialState(): AppState {
  return {
    ready: false,
    start: null,
    units: "in",
    machine: { ...NO_MACHINE },
    material: { x: 0, y: 0, width: 279.4, height: 215.9, reach: null, fits: null },
    paper: { size: "letter", orientation: "landscape", custom_width_mm: null, custom_height_mm: null },
    margin: 6.35,
    jobs: [],
    pieces: [],
    colors: [],
    selection: [],
    tool: "select",
    homing: false,
    jogStep: 1,
    linkScale: true,
    view: { grid: true, margins: true, original: false },
    notice: null,
    dialog: null,
    plot: { ...IDLE_PLOT },
    summary: null,
    preparing: false,
    prepareProblem: null,
    skipWhite: true,
    advanced: {},
    preview: null,
  };
}

export class Store<T extends object> {
  private readonly listeners = new Set<() => void>();

  constructor(public state: T) {}

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  update(change: Partial<T> | ((state: T) => Partial<T>)): void {
    const patch = typeof change === "function" ? change(this.state) : change;
    this.state = { ...this.state, ...patch };
    for (const listener of [...this.listeners]) listener();
  }
}

/** Re-renders a Lit component whenever the store changes. */
export class StoreController<T extends object> implements ReactiveController {
  private unsubscribe: (() => void) | null = null;

  constructor(
    private readonly host: ReactiveControllerHost,
    private readonly store: Store<T>,
  ) {
    host.addController(this);
  }

  hostConnected(): void {
    this.unsubscribe = this.store.subscribe(() => this.host.requestUpdate());
  }

  hostDisconnected(): void {
    this.unsubscribe?.();
    this.unsubscribe = null;
  }
}
