/** Pure helpers for the plate: hit testing, the marquee, handles, angles, paths and the grid. */
import type { Box, Handle, Point } from "../geometry/placement";
import { normalizeAngle, type Units } from "../geometry/units";

/** The drag-and-drop type for a job dragged from the Jobs list onto the plate. */
export const JOB_MIME = "application/x-rosetta-job";

/** Grid spacing in mm: a minor line, and a stronger one every `every` minor lines (spec §2.4). */
export const GRID: Record<Units, { minor: number; every: number }> = {
  in: { minor: 6.35, every: 4 }, // 1/4 in, stronger every inch
  mm: { minor: 10, every: 5 },
  cm: { minor: 10, every: 5 },
};

export interface IdBox {
  id: string;
  box: Box;
}

function contains(box: Box, [x, y]: Point): boolean {
  return x >= box.x && x <= box.x + box.width && y >= box.y && y <= box.y + box.height;
}

function overlaps(a: Box, b: Box): boolean {
  return a.x <= b.x + b.width && b.x <= a.x + a.width && a.y <= b.y + b.height && b.y <= a.y + a.height;
}

/** The topmost (last drawn) box containing the point. */
export function hitPiece(boxes: IdBox[], point: Point): string | null {
  for (let index = boxes.length - 1; index >= 0; index -= 1) {
    if (contains(boxes[index].box, point)) return boxes[index].id;
  }
  return null;
}

export function rectFrom(a: Point, b: Point): Box {
  return { x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), width: Math.abs(a[0] - b[0]), height: Math.abs(a[1] - b[1]) };
}

export function marqueeHits(boxes: IdBox[], rect: Box): string[] {
  return boxes.filter((item) => overlaps(item.box, rect)).map((item) => item.id);
}

/** The handle within `radius` screen px of the pointer, if any. */
export function handleAt(point: Point, handles: Readonly<Record<Handle, readonly [number, number]>>, radius = 6): Handle | null {
  for (const name of ["nw", "ne", "se", "sw"] as const) {
    const [hx, hy] = handles[name];
    if (Math.abs(point[0] - hx) <= radius && Math.abs(point[1] - hy) <= radius) return name;
  }
  return null;
}

/** Direction from center to point in degrees, clockwise on screen, 0 = toward +x. */
export function angleAt(center: Point, point: Point): number {
  return normalizeAngle((Math.atan2(point[1] - center[1], point[0] - center[0]) * 180) / Math.PI);
}

export function snapAngle(degrees: number, step: number): number {
  return normalizeAngle(Math.round(degrees / step) * step);
}

/** SVG path text for flat lines [x0, y0, x1, y1, …]. */
export function linesToPath(lines: number[][]): string {
  let text = "";
  for (const line of lines) {
    for (let index = 0; index + 1 < line.length; index += 2) {
      text += `${index === 0 ? "M" : "L"}${line[index]} ${line[index + 1]}`;
    }
  }
  return text;
}

/** Multiples of spacing from `from` to `to`. */
export function gridLines(from: number, to: number, spacing: number): number[] {
  const lines: number[] = [];
  for (let value = Math.ceil(from / spacing) * spacing; value <= to; value += spacing) {
    lines.push(Math.round(value / spacing) * spacing + 0); // + 0 turns -0 into 0
  }
  return lines;
}

export function unionBox(boxes: Box[]): Box | null {
  if (boxes.length === 0) return null;
  const x0 = Math.min(...boxes.map((b) => b.x));
  const y0 = Math.min(...boxes.map((b) => b.y));
  const x1 = Math.max(...boxes.map((b) => b.x + b.width));
  const y1 = Math.max(...boxes.map((b) => b.y + b.height));
  return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
}
