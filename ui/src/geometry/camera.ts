/** The plate's view: screen px = orient(machine mm) × scale + (x, y). */
import { machineToScreenDir, screenToMachineDir, type Orient } from "./orientation";
import type { Box, Point } from "./placement";

export interface Camera {
  scale: number;
  x: number;
  y: number;
  /** How the plate is turned to match the plotter; left out means the standard view. */
  orient?: Orient;
}
export interface Size {
  width: number;
  height: number;
}

export const MIN_SCALE = 0.05;
export const MAX_SCALE = 200;

const STANDARD: Orient = { a: 1, b: 0, c: 0, d: 1 };

function clampScale(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, Number.isFinite(scale) ? scale : MAX_SCALE));
}

/** The box's corners turned to screen directions (unscaled), as a bounding box. */
function turnedBounds(box: Box, orient: Orient): Box {
  const corners = ([[box.x, box.y], [box.x + box.width, box.y], [box.x + box.width, box.y + box.height], [box.x, box.y + box.height]] as Point[]).map(
    (p) => machineToScreenDir(orient, p),
  );
  const xs = corners.map((c) => c[0]);
  const ys = corners.map((c) => c[1]);
  return { x: Math.min(...xs), y: Math.min(...ys), width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys) };
}

export function fitCamera(box: Box, view: Size, padding = 32, orient: Orient = STANDARD): Camera {
  const turned = turnedBounds(box, orient);
  const scale = clampScale(
    Math.min((view.width - 2 * padding) / turned.width, (view.height - 2 * padding) / turned.height),
  );
  return {
    scale,
    x: (view.width - turned.width * scale) / 2 - turned.x * scale,
    y: (view.height - turned.height * scale) / 2 - turned.y * scale,
    orient,
  };
}

export function toScreen(camera: Camera, point: Point): Point {
  const [x, y] = machineToScreenDir(camera.orient ?? STANDARD, point);
  return [x * camera.scale + camera.x, y * camera.scale + camera.y];
}

export function toMachine(camera: Camera, point: Point): Point {
  return screenToMachineDir(camera.orient ?? STANDARD, [(point[0] - camera.x) / camera.scale, (point[1] - camera.y) / camera.scale]);
}

/** Zoom by factor, keeping the machine point under `screen` where it is. */
export function zoomAt(camera: Camera, factor: number, screen: Point): Camera {
  const scale = clampScale(camera.scale * factor);
  return {
    ...camera,
    scale,
    x: screen[0] - (screen[0] - camera.x) * (scale / camera.scale),
    y: screen[1] - (screen[1] - camera.y) * (scale / camera.scale),
  };
}

export function panBy(camera: Camera, dx: number, dy: number): Camera {
  return { ...camera, x: camera.x + dx, y: camera.y + dy };
}

/** The SVG transform that draws machine millimetres where the camera shows them. */
export function cameraMatrix(camera: Camera): string {
  const { a, b, c, d } = camera.orient ?? STANDARD;
  const s = camera.scale;
  return `matrix(${s * a + 0} ${s * c + 0} ${s * b + 0} ${s * d + 0} ${camera.x} ${camera.y})`;
}
