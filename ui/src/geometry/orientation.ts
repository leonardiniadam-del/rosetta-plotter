/**
 * How the plate is turned to match the plotter as the student faces it (orientation spec §1).
 * A code names the screen corner HOME sits in, then whether machine X runs across (h) or up and
 * down (v) from there. The eight codes cover every way a plotter can be mounted. Only the view
 * turns: placements, jobs and plots stay in machine millimetres.
 */
import type { Point } from "./placement";

export type Corner = "nw" | "ne" | "se" | "sw";
export type OrientationCode = `${Corner}-${"h" | "v"}`;

export const ORIENTATIONS: OrientationCode[] = ["nw-h", "nw-v", "ne-h", "ne-v", "se-h", "se-v", "sw-h", "sw-v"];
export const DEFAULT_ORIENTATION: OrientationCode = "nw-h";

/** Screen direction = [a·x + b·y, c·x + d·y] for a machine direction (x, y). Entries are −1, 0 or 1. */
export interface Orient {
  a: number;
  b: number;
  c: number;
  d: number;
}

export function isOrientation(value: unknown): value is OrientationCode {
  return typeof value === "string" && (ORIENTATIONS as string[]).includes(value);
}

/** Machine X runs away from HOME along one edge of its corner, and machine Y along the other. */
export function orientMatrix(code: OrientationCode): Orient {
  const right = code[1] === "w" ? 1 : -1; // from a west corner the paper lies to the right
  const down = code[0] === "n" ? 1 : -1; // from a north corner it lies below
  return code.endsWith("-h") ? { a: right, b: 0, c: 0, d: down } : { a: 0, b: right, c: down, d: 0 };
}

export function machineToScreenDir(o: Orient, [x, y]: Point): Point {
  return [o.a * x + o.b * y, o.c * x + o.d * y];
}

/** The inverse, which for these turns and mirrors is the transpose. */
export function screenToMachineDir(o: Orient, [x, y]: Point): Point {
  return [o.a * x + o.c * y, o.b * x + o.d * y];
}

export function neighbours(corner: Corner): [Corner, Corner] {
  const across: Corner = `${corner[0]}${corner[1] === "w" ? "e" : "w"}` as Corner;
  const upDown: Corner = `${corner[0] === "n" ? "s" : "n"}${corner[1]}` as Corner;
  return [across, upDown];
}

/** HOME's corner and the corner X runs toward; null unless they share an edge. */
export function codeFromPicks(home: Corner, toward: Corner): OrientationCode | null {
  const [across, upDown] = neighbours(home);
  if (toward === across) return `${home}-h`;
  if (toward === upDown) return `${home}-v`;
  return null;
}
