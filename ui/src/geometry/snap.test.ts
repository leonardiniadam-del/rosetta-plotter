import { describe, expect, it } from "vitest";
import { snapDrag, toEdge } from "./snap";

const paper = { width: 200, height: 100, margin: 10 };
const box = { x: 50, y: 40, width: 40, height: 20 };

describe("snapDrag", () => {
  it("leaves a drag alone away from every guide", () => {
    expect(snapDrag(box, 7, 3, paper, 2)).toEqual([7, 3]);
  });

  it("snaps the left edge to the paper's edge and to the margin", () => {
    expect(snapDrag(box, -49, 0, paper, 2)[0]).toBe(-50);
    expect(snapDrag(box, -41.5, 0, paper, 2)[0]).toBe(-40);
  });

  it("snaps the right and bottom edges to the far paper edges", () => {
    expect(snapDrag(box, 109, 39, paper, 2)).toEqual([110, 40]);
  });

  it("snaps the middle to the paper's center line", () => {
    expect(snapDrag(box, 31, 0, paper, 2)[0]).toBe(30);
    expect(snapDrag(box, 0, 1, paper, 2)[1]).toBe(0);
  });

  it("each axis snaps on its own", () => {
    expect(snapDrag(box, -49, 13, paper, 2)).toEqual([-50, 13]);
  });

  it("takes the closer guide", () => {
    // 40 wide, between the margin (10) and the edge (0): 1.2 from the margin, 8.8 from the edge.
    expect(snapDrag(box, -38.8, 0, paper, 10)[0]).toBe(-40);
  });

  it("with no tolerance never moves the drag", () => {
    expect(snapDrag(box, -49.9, 0, paper, 0)).toEqual([-49.9, 0]);
  });
});

describe("toEdge", () => {
  it("moves the box flush against each paper edge", () => {
    expect(toEdge(box, "left", paper)).toEqual([-50, 0]);
    expect(toEdge(box, "right", paper)).toEqual([110, 0]);
    expect(toEdge(box, "top", paper)).toEqual([0, -40]);
    expect(toEdge(box, "bottom", paper)).toEqual([0, 40]);
  });

  it("can stop at the margin", () => {
    expect(toEdge(box, "right", paper, 10)).toEqual([100, 0]);
  });
});
