/** Why a control can't work right now (manager UI spec §6), or null if it can. Shown as its tooltip. */
import { plotRunning } from "./selectors";
import type { AppState } from "./store";

export type Control =
  | "start"
  | "pause"
  | "stop"
  | "preview"
  | "paper"
  | "setHome"
  | "move"
  | "trace"
  | "arrange"
  | "markCorner"
  | "rotatePaper"
  | "orientation"
  | "model";

const NO_PLOTTER = "No plotter connected. Plug in the USB cable and the power adapter.";
const NO_MODEL = "Model unknown. Choose it in Plotter › Plotter model…";
const NO_POWER = "The power adapter isn't plugged in.";
const NO_HOME = "Home not set. Use Set Home first.";
const NOTHING = "Nothing placed on the paper.";
const NO_PENS = "No pens are turned on in the Pens panel.";
const RUNNING = "A plot is running.";
const NO_SELECTION = "Select a drawing first.";
const PREPARING = "The plot is being prepared.";
const NOT_READY = "The plot isn't ready yet.";
const NOT_PLOTTING = "Not plotting.";
const NOT_PLOTTING_OR_TRACING = "Not plotting or tracing.";

export function disabledReason(control: Control, s: AppState): string | null {
  const machine = s.machine.state;
  const checks: Record<Control, [boolean, string][]> = {
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
    pause: [[!["plotting", "homing"].includes(s.plot.state), NOT_PLOTTING]],
    stop: [[!["plotting", "homing", "tracing"].includes(s.plot.state), NOT_PLOTTING_OR_TRACING]],
    preview: [
      [s.pieces.length === 0, NOTHING],
      [plotRunning(s), RUNNING],
      [s.preparing, PREPARING],
      [s.summary === null, "Times aren't ready yet."],
    ],
    paper: [[plotRunning(s), RUNNING]],
    setHome: [
      [machine === "no_plotter", NO_PLOTTER],
      [machine === "needs_model", NO_MODEL],
      [plotRunning(s), RUNNING],
    ],
    move: [
      [machine === "no_plotter", NO_PLOTTER],
      [machine === "needs_model", NO_MODEL],
      [plotRunning(s), RUNNING],
      [machine === "not_homed", NO_HOME],
    ],
    trace: [
      [machine === "no_plotter", NO_PLOTTER],
      [plotRunning(s), RUNNING],
      [machine !== "ready", NO_HOME],
      [s.pieces.length === 0, NOTHING],
      [s.preparing || s.summary === null, NOT_READY],
    ],
    arrange: [
      [s.selection.length === 0, NO_SELECTION],
      [plotRunning(s), RUNNING],
    ],
    markCorner: [
      [plotRunning(s), RUNNING],
      [machine !== "ready", NO_HOME],
    ],
    rotatePaper: [[plotRunning(s), RUNNING]],
    orientation: [[plotRunning(s), RUNNING]],
    model: [
      [machine === "no_plotter", NO_PLOTTER],
      [plotRunning(s), RUNNING],
    ],
  };
  return checks[control].find(([applies]) => applies)?.[1] ?? null;
}
