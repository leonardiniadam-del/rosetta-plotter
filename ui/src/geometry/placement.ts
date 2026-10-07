/**
 * Where placed drawings land: the same math as rosetta.geometry.place_point, so the screen shows exactly
 * what will be plotted. Units are mm; y grows toward the student; angles turn clockwise on screen.
 * A placement scales the artwork on its own axes (scale across, scale_y down), turns it, and puts the
 * top-left of its upright box at (x, y) from the paper's corner nearest Home.
 */
import { normalizeAngle } from "./units";

export type Point = [number, number];
export interface Placement {
  x: number;
  y: number;
  scale: number;
  scale_y: number;
  rotation: number;
}
export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}
/** An SVG matrix(a b c d e f): x' = a·x + c·y + e, y' = b·x + d·y + f. */
export type Matrix = [number, number, number, number, number, number];
export type Handle = "nw" | "ne" | "se" | "sw";

export const MIN_SIZE_MM = 0.5;

/** The largest scale Python accepts (session.MAX_SCALE): 100×, shown as 10000%. */
export const MAX_SCALE = 100;

const QUARTER: Record<number, Point> = { 0: [1, 0], 90: [0, 1], 180: [-1, 0], 270: [0, -1] };

export function isQuarterTurn(rotation: number): boolean {
  return normalizeAngle(rotation) in QUARTER;
}

/** Exact for quarter turns, like Python's _cos_sin. */
function cosSin(rotation: number): Point {
  const turn = normalizeAngle(rotation);
  const exact = QUARTER[turn];
  if (exact) return exact;
  const radians = (turn * Math.PI) / 180;
  return [Math.cos(radians), Math.sin(radians)];
}

/** Size of the upright box around a width × height frame turned by rotation degrees. */
export function rotatedSize(width: number, height: number, rotation: number): Point {
  const [cos, sin] = cosSin(rotation).map(Math.abs) as Point;
  return [width * cos + height * sin, width * sin + height * cos];
}

/** Artwork mm → machine mm, as an SVG matrix. origin is the paper's corner nearest Home. */
export function pieceMatrix(artWidth: number, artHeight: number, placement: Placement, origin: Point): Matrix {
  const [cos, sin] = cosSin(placement.rotation);
  const a = cos * placement.scale;
  const b = sin * placement.scale;
  const c = -sin * placement.scale_y;
  const d = cos * placement.scale_y;
  const xs = [0, a * artWidth, a * artWidth + c * artHeight, c * artHeight];
  const ys = [0, b * artWidth, b * artWidth + d * artHeight, d * artHeight];
  return [a, b, c, d, origin[0] + placement.x - Math.min(...xs), origin[1] + placement.y - Math.min(...ys)];
}

export function applyMatrix(matrix: Matrix, point: Point): Point {
  const [a, b, c, d, e, f] = matrix;
  return [a * point[0] + c * point[1] + e, b * point[0] + d * point[1] + f];
}

export function placePoint(point: Point, artWidth: number, artHeight: number, placement: Placement, origin: Point): Point {
  return applyMatrix(pieceMatrix(artWidth, artHeight, placement, origin), point);
}

/** The drawing's upright box, from the paper's corner (like Placement's x, y). */
export function pieceBox(artWidth: number, artHeight: number, placement: Placement): Box {
  const [width, height] = rotatedSize(artWidth * placement.scale, artHeight * placement.scale_y, placement.rotation);
  return { x: placement.x, y: placement.y, width, height };
}

/** Turn a drawing to a new angle about its center. */
export function rotateAboutCenter(artWidth: number, artHeight: number, placement: Placement, rotation: number): Placement {
  const box = pieceBox(artWidth, artHeight, placement);
  const turned = { ...placement, rotation: normalizeAngle(rotation) };
  const next = pieceBox(artWidth, artHeight, turned);
  return { ...turned, x: box.x + (box.width - next.width) / 2, y: box.y + (box.height - next.height) / 2 };
}

/**
 * A typed W and/or H for the drawing's upright box, keeping its top-left.
 * Linked: both scales change by one factor (from W if given, else H).
 * Unlinked: stretches along the drawing's own sides, which needs a quarter turn (null otherwise).
 * Null too for sizes that aren't above zero.
 */
export function resizeBox(
  artWidth: number,
  artHeight: number,
  placement: Placement,
  size: { width?: number; height?: number },
  linked: boolean,
): Placement | null {
  const box = pieceBox(artWidth, artHeight, placement);
  if (linked) {
    const factor = size.width !== undefined ? size.width / box.width : size.height !== undefined ? size.height / box.height : 1;
    if (!(factor > 0) || !Number.isFinite(factor)) return null;
    return { ...placement, scale: placement.scale * factor, scale_y: placement.scale_y * factor };
  }
  if (!isQuarterTurn(placement.rotation)) return null;
  const turn = normalizeAngle(placement.rotation);
  const widthIsOwnWidth = turn === 0 || turn === 180;
  let { scale, scale_y } = placement;
  if (size.width !== undefined) {
    if (widthIsOwnWidth) scale = size.width / artWidth;
    else scale_y = size.width / artHeight;
  }
  if (size.height !== undefined) {
    if (widthIsOwnWidth) scale_y = size.height / artHeight;
    else scale = size.height / artWidth;
  }
  if (!(scale > 0 && scale_y > 0) || !Number.isFinite(scale) || !Number.isFinite(scale_y)) return null;
  return { ...placement, scale, scale_y };
}

/**
 * Dragging a corner handle to `pointer` (paper mm) with the opposite corner fixed. Stretches freely at a
 * quarter turn unless keepProportions (Shift); always keeps proportions at a free angle. Never smaller than
 * MIN_SIZE_MM on a side.
 */
export function scaleFromHandle(
  artWidth: number,
  artHeight: number,
  placement: Placement,
  handle: Handle,
  pointer: Point,
  keepProportions: boolean,
): Placement {
  const box = pieceBox(artWidth, artHeight, placement);
  const west = handle === "nw" || handle === "sw";
  const north = handle === "nw" || handle === "ne";
  const fixedX = west ? box.x + box.width : box.x;
  const fixedY = north ? box.y + box.height : box.y;
  const width = Math.max(MIN_SIZE_MM, Math.abs(pointer[0] - fixedX));
  const height = Math.max(MIN_SIZE_MM, Math.abs(pointer[1] - fixedY));
  let resized: Placement | null;
  if (keepProportions || !isQuarterTurn(placement.rotation)) {
    const factor = Math.max(width / box.width, height / box.height);
    resized = resizeBox(artWidth, artHeight, placement, { width: box.width * factor }, true);
  } else {
    resized = resizeBox(artWidth, artHeight, placement, { width, height }, false);
  }
  const next = resized ?? placement;
  const size = pieceBox(artWidth, artHeight, next);
  return { ...next, x: west ? fixedX - size.width : fixedX, y: north ? fixedY - size.height : fixedY };
}
