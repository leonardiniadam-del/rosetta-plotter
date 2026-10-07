import { describe, expect, it } from "vitest";
import fixtures from "./fixtures.json";
import {
  isQuarterTurn,
  pieceBox,
  placePoint,
  resizeBox,
  rotateAboutCenter,
  rotatedSize,
  scaleFromHandle,
  type Placement,
  type Point,
} from "./placement";

const [ART_W, ART_H] = fixtures.art as [number, number];
const ORIGIN = fixtures.origin as Point;
const upright: Placement = { x: 10, y: 20, scale: 1, scale_y: 1, rotation: 0 };

describe("matches rosetta.geometry", () => {
  for (const c of fixtures.cases) {
    it(JSON.stringify(c.placement), () => {
      const p = c.placement as Placement;
      const size = rotatedSize(ART_W * p.scale, ART_H * p.scale_y, p.rotation);
      expect(size[0]).toBeCloseTo(c.size[0], 9);
      expect(size[1]).toBeCloseTo(c.size[1], 9);
      for (const [point, expected] of c.points as [Point, Point][]) {
        const placed = placePoint(point, ART_W, ART_H, p, ORIGIN);
        expect(placed[0]).toBeCloseTo(expected[0], 9);
        expect(placed[1]).toBeCloseTo(expected[1], 9);
      }
    });
  }
});

describe("editing", () => {
  it("knows quarter turns", () => {
    expect([0, 90, 180, 270, 450, -90].every(isQuarterTurn)).toBe(true);
    expect(isQuarterTurn(33.5)).toBe(false);
  });

  it("turns a drawing about its center", () => {
    const before = pieceBox(ART_W, ART_H, upright);
    const turned = rotateAboutCenter(ART_W, ART_H, upright, 90);
    const after = pieceBox(ART_W, ART_H, turned);
    expect(turned.rotation).toBe(90);
    expect(after.x + after.width / 2).toBeCloseTo(before.x + before.width / 2);
    expect(after.y + after.height / 2).toBeCloseTo(before.y + before.height / 2);
    expect([after.width, after.height]).toEqual([20, 40]);
  });

  it("resizes proportionally while linked, keeping the top-left", () => {
    const next = resizeBox(ART_W, ART_H, upright, { width: 80 }, true)!;
    expect([next.scale, next.scale_y, next.x, next.y]).toEqual([2, 2, 10, 20]);
  });

  it("stretches one side while unlinked, along the drawing's own sides", () => {
    expect(resizeBox(ART_W, ART_H, upright, { height: 40 }, false)).toMatchObject({ scale: 1, scale_y: 2 });
    const quarter = { ...upright, rotation: 90 };
    // At 90° the box's width is the drawing's own height.
    expect(resizeBox(ART_W, ART_H, quarter, { width: 40 }, false)).toMatchObject({ scale: 1, scale_y: 2 });
    expect(resizeBox(ART_W, ART_H, { ...upright, rotation: 30 }, { width: 50 }, false)).toBeNull();
    expect(resizeBox(ART_W, ART_H, upright, { width: -5 }, true)).toBeNull();
  });

  it("drags a corner handle with the opposite corner fixed", () => {
    // Box is 10..50 x 20..40. Drag the SE corner to (90, 30): free stretch.
    const stretched = scaleFromHandle(ART_W, ART_H, upright, "se", [90, 30], false);
    expect(pieceBox(ART_W, ART_H, stretched)).toEqual({ x: 10, y: 20, width: 80, height: 10 });
    // With Shift the larger change wins and proportions hold.
    const kept = scaleFromHandle(ART_W, ART_H, upright, "se", [90, 30], true);
    expect(pieceBox(ART_W, ART_H, kept)).toEqual({ x: 10, y: 20, width: 80, height: 40 });
    // Dragging NW keeps the SE corner where it was.
    const nw = scaleFromHandle(ART_W, ART_H, upright, "nw", [0, 10], true);
    const box = pieceBox(ART_W, ART_H, nw);
    expect([box.x + box.width, box.y + box.height]).toEqual([50, 40]);
  });

  it("keeps proportions at a free angle even without Shift", () => {
    const turned = { ...upright, rotation: 30 };
    const next = scaleFromHandle(ART_W, ART_H, turned, "se", [200, 60], false);
    expect(next.scale).toBeCloseTo(next.scale_y);
  });
});
