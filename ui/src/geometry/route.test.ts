import { describe, expect, it } from "vitest";
import type { PlotSummary } from "../bridge/contract";
import { pointAt, routeOf, routePath, timeAtPendown } from "./route";

const summary: PlotSummary = {
  layers: [
    {
      layer: 1, color: "#000000", name: "black", seconds: 2, pendown_mm: 10,
      path: [
        { down: false, points: [0, 0, 0, 10, 0, 1] },
        { down: true, points: [10, 0, 1, 10, 10, 2] },
      ],
    },
    { layer: 2, color: "#ff0000", name: "red", seconds: 2, pendown_mm: 5, path: [{ down: true, points: [0, 0, 0, 0, 5, 1] }] },
  ],
  total_seconds: 4,
  ink_bbox: [0, 0, 10, 10],
  warnings: [],
};

describe("route", () => {
  it("puts the pens one after another on one timeline", () => {
    const route = routeOf(summary);
    expect(route.total).toBe(4);
    expect(route.layerStarts).toEqual([0, 2]);
    expect(routeOf(summary)).toBe(route); // cached
  });

  it("finds the pen at a time", () => {
    const route = routeOf(summary);
    expect(pointAt(route, 0)).toEqual([0, 0]);
    expect(pointAt(route, 1.5)).toEqual([10, 5]);
    expect(pointAt(route, 2.5)).toEqual([0, 2.5]);
    expect(pointAt(route, 99)).toEqual([0, 5]);
  });

  it("draws one pen's moves, all of them or up to a time", () => {
    const route = routeOf(summary);
    expect(routePath(route, 0, true)).toBe("M10 0L10 10");
    expect(routePath(route, 0, true, 1.5)).toBe("M10 0L10 5");
    expect(routePath(route, 0, false)).toBe("M0 0L10 0");
    expect(routePath(route, 1, true, 2)).toBe("");
  });
  it("finds the time a pen has drawn a distance, whatever the pen-up travel before it", () => {
    const route = routeOf(summary);
    // Black: a 1 s pen-up move, then 10 mm drawn in the next second.
    expect(timeAtPendown(route, 0, 0)).toBe(1);
    expect(timeAtPendown(route, 0, 5)).toBe(1.5);
    expect(timeAtPendown(route, 0, 10)).toBe(2);
    expect(timeAtPendown(route, 0, 99)).toBe(2);
    // Red starts at 2 s on the whole timeline.
    expect(timeAtPendown(route, 1, 2.5)).toBe(2.5);
    expect(routePath(route, 0, true, timeAtPendown(route, 0, 0))).toBe("");
  });

  it("builds a pen's whole path once", () => {
    const route = routeOf(summary);
    expect(routePath(route, 0, true)).toBe(routePath(route, 0, true));
    expect(routePath(route, 1, false)).toBe("");
  });
});
