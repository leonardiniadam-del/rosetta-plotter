/** The plate's view: screen px = machine mm × scale + (x, y). */
import type { Box, Point } from "./placement";

export interface Camera {
  scale: number;
  x: number;
  y: number;
}
export interface Size {
  width: number;
  height: number;
}

export const MIN_SCALE = 0.05;
export const MAX_SCALE = 200;

function clampScale(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, Number.isFinite(scale) ? scale : MAX_SCALE));
}

export function fitCamera(box: Box, view: Size, padding = 32): Camera {
  const scale = clampScale(
    Math.min((view.width - 2 * padding) / box.width, (view.height - 2 * padding) / box.height),
  );
  return {
    scale,
    x: (view.width - box.width * scale) / 2 - box.x * scale,
    y: (view.height - box.height * scale) / 2 - box.y * scale,
  };
}

export function toScreen(camera: Camera, point: Point): Point {
  return [point[0] * camera.scale + camera.x, point[1] * camera.scale + camera.y];
}

export function toMachine(camera: Camera, point: Point): Point {
  return [(point[0] - camera.x) / camera.scale, (point[1] - camera.y) / camera.scale];
}

/** Zoom by factor, keeping the machine point under `screen` where it is. */
export function zoomAt(camera: Camera, factor: number, screen: Point): Camera {
  const scale = clampScale(camera.scale * factor);
  const [mx, my] = toMachine(camera, screen);
  return { scale, x: screen[0] - mx * scale, y: screen[1] - my * scale };
}

export function panBy(camera: Camera, dx: number, dy: number): Camera {
  return { ...camera, x: camera.x + dx, y: camera.y + dy };
}
