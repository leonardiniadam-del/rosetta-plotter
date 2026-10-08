import { describe, expect, it } from "vitest";
import { angleAt, GRID, gridLines, handleAt, hitPiece, linesToPath, marqueeHits, rectFrom, snapAngle, unionBox } from "./interaction";

const boxes = [
  { id: "a", box: { x: 0, y: 0, width: 50, height: 50 } },
  { id: "b", box: { x: 40, y: 40, width: 50, height: 50 } },
];

describe("plate helpers", () => {
  it("hits the topmost drawing", () => {
    expect(hitPiece(boxes, [45, 45])).toBe("b");
    expect(hitPiece(boxes, [10, 10])).toBe("a");
    expect(hitPiece(boxes, [200, 200])).toBeNull();
  });

  it("selects what a marquee touches", () => {
    expect(marqueeHits(boxes, rectFrom([60, 60], [100, 100]))).toEqual(["b"]);
    expect(marqueeHits(boxes, rectFrom([100, 100], [-1, -1]))).toEqual(["a", "b"]);
  });

  it("the inch grid has a stronger line every inch", () => {
    expect(GRID.in.minor * GRID.in.every).toBeCloseTo(25.4);
    expect(GRID.mm.minor * GRID.mm.every).toBe(50);
    expect(GRID.cm.minor * GRID.cm.every).toBe(50);
  });

  it("finds a handle near the pointer", () => {
    const handles = { nw: [0, 0], ne: [100, 0], se: [100, 50], sw: [0, 50] } as const;
    expect(handleAt([103, 48], handles)).toBe("se");
    expect(handleAt([50, 25], handles)).toBeNull();
  });

  it("measures angles clockwise on screen and snaps them", () => {
    expect(angleAt([0, 0], [10, 0])).toBe(0);
    expect(angleAt([0, 0], [0, 10])).toBe(90);
    expect(snapAngle(37, 15)).toBe(30);
    expect(snapAngle(-8, 15)).toBe(345);
  });

  it("writes SVG paths from flat line lists", () => {
    expect(linesToPath([[0, 0, 10, 0, 10, 5], [1, 1, 2, 2]])).toBe("M0 0L10 0L10 5M1 1L2 2");
    expect(linesToPath([])).toBe("");
  });

  it("lists grid lines in a range", () => {
    expect(gridLines(-3, 25, 10)).toEqual([0, 10, 20]);
  });

  it("joins boxes", () => {
    expect(unionBox(boxes.map((b) => b.box))).toEqual({ x: 0, y: 0, width: 90, height: 90 });
    expect(unionBox([])).toBeNull();
  });
});
