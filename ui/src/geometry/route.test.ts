import { describe, expect, it } from "vitest";
import type { PlotSummary } from "../bridge/contract";
import { pointAt, routeOf, routePath } from "./route";

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
});
