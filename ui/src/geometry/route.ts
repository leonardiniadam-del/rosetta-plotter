/**
 * The prepared plot's planned route (bridge.md summary.path) as one timeline: pen after pen, times in
 * seconds from the start of the whole plot, points in machine mm from Home. Used to show the lines
 * already drawn during a plot, and by Preview path.
 */
import type { PlotSummary } from "../bridge/contract";
import type { Point } from "./placement";

export interface Segment {
  layer: number;
  down: boolean;
  x0: number;
  y0: number;
  t0: number;
  x1: number;
  y1: number;
  t1: number;
  /** The pen's pen-down distance in mm (within its own pen) at the start and the end of this move. */
  d0: number;
  d1: number;
}

export interface Route {
  segments: Segment[];
  /** The same segments, grouped by pen, in order. */
  byLayer: Segment[][];
  total: number;
  /** When each pen starts, in seconds from the start of the plot. */
  layerStarts: number[];
}

const cache = new WeakMap<PlotSummary, Route>();

export function routeOf(summary: PlotSummary): Route {
  const known = cache.get(summary);
  if (known) return known;
  const segments: Segment[] = [];
  const byLayer: Segment[][] = [];
  const layerStarts: number[] = [];
  let offset = 0;
  summary.layers.forEach((layer, index) => {
    layerStarts.push(offset);
    let end = 0;
    let drawn = 0;
    const own: Segment[] = [];
    byLayer.push(own);
    for (const run of layer.path) {
      const p = run.points;
      for (let i = 0; i + 5 < p.length; i += 3) {
        const d0 = drawn;
        if (run.down) drawn += Math.hypot(p[i + 3] - p[i], p[i + 4] - p[i + 1]);
        const seg = { layer: index, down: run.down, x0: p[i], y0: p[i + 1], t0: offset + p[i + 2], x1: p[i + 3], y1: p[i + 4], t1: offset + p[i + 5], d0, d1: drawn };
        segments.push(seg);
        own.push(seg);
        end = Math.max(end, p[i + 5]);
      }
    }
    offset += Math.max(layer.seconds, end);
  });
  const route = { segments, byLayer, total: offset, layerStarts };
  cache.set(summary, route);
  return route;
}

function along(seg: Segment, t: number): Point {
  if (t >= seg.t1) return [seg.x1, seg.y1];
  const k = seg.t1 > seg.t0 ? (t - seg.t0) / (seg.t1 - seg.t0) : 1;
  return [seg.x0 + (seg.x1 - seg.x0) * k, seg.y0 + (seg.y1 - seg.y0) * k];
}

/** Where the pen is at time t. */
export function pointAt(route: Route, t: number): Point | null {
  const s = route.segments;
  if (s.length === 0) return null;
  if (t <= s[0].t0) return [s[0].x0, s[0].y0];
  let lo = 0;
  let hi = s.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (s[mid].t1 < t) lo = mid + 1;
    else hi = mid;
  }
  return along(s[lo], t);
}

/** The time at which a pen has drawn `mm` of pen-down distance (past its end: when it last drew). */
export function timeAtPendown(route: Route, layer: number, mm: number): number {
  const own = route.byLayer[layer];
  if (!own) return 0;
  let last: Segment | null = null;
  for (const seg of own) {
    if (!seg.down) continue;
    if (seg.d1 >= mm) {
      if (mm <= seg.d0 || seg.d1 <= seg.d0) return seg.t0;
      return seg.t0 + ((mm - seg.d0) / (seg.d1 - seg.d0)) * (seg.t1 - seg.t0);
    }
    last = seg;
  }
  return last ? last.t1 : route.layerStarts[layer];
}

const wholePaths = new WeakMap<Route, Map<string, string>>();

/** An SVG path of one pen's pen-down (or pen-up) moves, up to time `until`. The whole path is built once. */
export function routePath(route: Route, layer: number, down: boolean, until = Infinity): string {
  if (until === Infinity) {
    let known = wholePaths.get(route);
    if (!known) wholePaths.set(route, (known = new Map()));
    const key = `${layer}|${down}`;
    let d = known.get(key);
    if (d === undefined) known.set(key, (d = build(route, layer, down, until)));
    return d;
  }
  return build(route, layer, down, until);
}

function build(route: Route, layer: number, down: boolean, until: number): string {
  const parts: string[] = [];
  let last: Point | null = null;
  for (const seg of route.byLayer[layer] ?? []) {
    if (seg.down !== down || seg.t0 >= until) continue;
    const end = along(seg, until);
    if (!last || last[0] !== seg.x0 || last[1] !== seg.y0) parts.push(`M${seg.x0} ${seg.y0}`);
    parts.push(`L${end[0]} ${end[1]}`);
    last = end;
  }
  return parts.join("");
}
