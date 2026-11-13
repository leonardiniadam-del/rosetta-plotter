/** Questions about the state that several parts of the page ask. */
import type { JobInfo, PieceInfo } from "../bridge/contract";
import { unionBox } from "../canvas/interaction";
import { pieceBox, type Box } from "../geometry/placement";
import { AT_REST } from "./plotting";
import type { AppState } from "./store";

export function jobOf(state: AppState, piece: PieceInfo): JobInfo | undefined {
  return state.jobs.find((job) => job.id === piece.job_id);
}

/** The connected model's reach in mm (x along the rail, y toward the student), or null without one. */
export function reachOf(state: AppState): [number, number] | null {
  const model = state.start?.models.find((m) => m.number === state.machine.model);
  return model ? [model.travel[0], model.travel[1]] : state.material.reach;
}

/** A piece's upright box from the paper's corner. */
export function pieceBoxOnPaper(state: AppState, piece: PieceInfo): Box {
  const job = jobOf(state, piece);
  return job ? pieceBox(job.width_mm, job.height_mm, piece.placement) : { x: piece.placement.x, y: piece.placement.y, width: 0, height: 0 };
}

export function selectedPieces(state: AppState): PieceInfo[] {
  return state.pieces.filter((piece) => state.selection.includes(piece.id));
}

/** The box around every selected piece, from the paper's corner. */
export function selectionBox(state: AppState): Box | null {
  return unionBox(selectedPieces(state).map((piece) => pieceBoxOnPaper(state, piece)));
}

export function plotRunning(state: AppState): boolean {
  return state.machine.state === "plotting" || !AT_REST.includes(state.plot.state);
}

/** A dialog has the window's attention: shortcuts wait. */
export function modalOpen(state: AppState): boolean {
  return state.dialog !== null;
}

/** A pen is asked for: the Plotter panel moves the pen so a new nib can be put on lines already drawn. */
export function penChange(state: AppState): boolean {
  return state.plot.state === "load_pen";
}
