import { describe, expect, it } from "vitest";
import "./plate";
import { toScreen } from "../geometry/camera";
import { orientMatrix, screenToMachineDir, type OrientationCode } from "../geometry/orientation";
import { pieceMatrix, type Point } from "../geometry/placement";
import { mount, readyToPlot, settle, shadow, startApp } from "../test/setup";
import type { RpPlate } from "./plate";

async function plateIn(code: OrientationCode) {
  const started = await startApp();
  await started.app.importFiles();
  await started.app.placeJob("job-1"); // 120 x 80 at (6.35, 6.35)
  const plate = await mount<RpPlate>("rp-plate");
  await started.app.setPlotterOrientation(code);
  await settle();
  const root = shadow(plate);
  return { ...started, plate, root, svg: root.querySelector("svg") as SVGSVGElement };
}

function pointer(svg: Element, type: string, [x, y]: Point, extra: MouseEventInit = {}) {
  svg.dispatchEvent(new MouseEvent(type, { clientX: x, clientY: y, button: 0, bubbles: true, ...extra }));
}

/** The drawing's centre on screen (machine (66.35, 46.35)). */
const CENTRE: Point = [66.35, 46.35];

describe("rp-plate in a turned orientation", () => {
  it.each(["ne-h", "sw-v", "se-v"] as OrientationCode[])("in %s, dragging right on screen moves the drawing right on screen", async (code) => {
    const { fake, plate, svg } = await plateIn(code);
    const from = toScreen(plate.view, CENTRE);
    pointer(svg, "pointerdown", from);
    pointer(svg, "pointermove", [from[0] + 40, from[1]]);
    pointer(svg, "pointerup", [from[0] + 40, from[1]]);
    await settle();
    const [, x, y] = fake.called("piece_place").at(-1) as [string, number, number];
    const [dx, dy] = screenToMachineDir(orientMatrix(code), [40 / plate.view.scale, 0]);
    expect(x).toBeCloseTo(6.35 + dx);
    expect(y).toBeCloseTo(6.35 + dy);
  });

  it("outlines the selection where the drawing is, with a positive size", async () => {
    const { plate, root } = await plateIn("ne-h");
    const outline = root.querySelector("rect.selection") as SVGRectElement;
    const [left] = toScreen(plate.view, [126.35, 6.35]);
    expect(Number(outline.getAttribute("x"))).toBeCloseTo(left);
    expect(Number(outline.getAttribute("width"))).toBeCloseTo(120 * plate.view.scale);
  });

  it("outlines a quarter-turned view with the sides swapped", async () => {
    const { plate, root } = await plateIn("nw-v");
    const outline = root.querySelector("rect.selection") as SVGRectElement;
    expect(Number(outline.getAttribute("width"))).toBeCloseTo(80 * plate.view.scale);
    expect(Number(outline.getAttribute("height"))).toBeCloseTo(120 * plate.view.scale);
  });

  it("draws the grid across the whole window when X runs right to left", async () => {
    const { root } = await plateIn("ne-h");
    const xs = Array.from(root.querySelectorAll("line.minor"))
      .filter((l) => l.getAttribute("x1") === l.getAttribute("x2"))
      .map((l) => Number(l.getAttribute("x1")));
    expect(xs.length).toBeGreaterThan(0);
  });

  it("in a mirrored view the Rotate tool turns the drawing the way the mouse goes", async () => {
    const { app, fake, plate, svg } = await plateIn("ne-h");
    app.setTool("rotate");
    await settle();
    const centre = toScreen(plate.view, CENTRE);
    const start: Point = [centre[0] + 50, centre[1]];
    const end: Point = [centre[0], centre[1] + 50]; // a quarter turn clockwise on screen
    const corner = (placement: Parameters<typeof pieceMatrix>[2]) => {
      const [a, b, , , e, f] = pieceMatrix(120, 80, placement, [0, 0]);
      return toScreen(plate.view, [a * 120 + e, b * 120 + f]); // the drawing's own top-right corner
    };
    const before = corner(app.state.pieces[0].placement);
    pointer(svg, "pointerdown", start);
    pointer(svg, "pointermove", end);
    pointer(svg, "pointerup", end);
    await settle();
    expect(fake.called("piece_place")).not.toHaveLength(0);
    const after = corner(app.state.pieces[0].placement);
    const v0 = [before[0] - centre[0], before[1] - centre[1]];
    const v1 = [after[0] - centre[0], after[1] - centre[1]];
    expect(v0[0] * v1[1] - v0[1] * v1[0]).toBeGreaterThan(0); // clockwise on screen (y runs down)
  });

  it("re-fits when the orientation changes after it has fitted", async () => {
    const { app, plate, root } = await plateIn("nw-h");
    app.requestView({ kind: "fit-paper" });
    await settle();
    await app.setPlotterOrientation("ne-v");
    await settle();
    const paper = root.querySelector("rect.paper") as SVGRectElement;
    expect(paper).not.toBeNull();
    const { material } = app.state;
    const a = toScreen(plate.view, [material.x, material.y]);
    const b = toScreen(plate.view, [material.x + material.width, material.y + material.height]);
    expect((a[0] + b[0]) / 2).toBeCloseTo(400, 0);
    expect((a[1] + b[1]) / 2).toBeCloseTo(300, 0);
    expect(Math.abs(b[1] - a[1])).toBeCloseTo(material.width * plate.view.scale); // the paper's width now runs down
  });

  it("never changes the prepared plot", async () => {
    const { app } = await readyToPlot();
    const before = app.state.summary;
    expect(before).not.toBeNull();
    await app.setPlotterOrientation("se-v");
    await settle();
    await settle();
    expect(app.state.summary).toBe(before);
  });
});

describe("rp-plate while picking the orientation", () => {
  it("marks four corners, then the two next to HOME's, and a click picks one", async () => {
    const { app, root, svg } = await plateIn("nw-h");
    app.startOrienting();
    await settle();
    const picks = () => Array.from(root.querySelectorAll("rect.pick:not(.chosen)")) as SVGRectElement[];
    expect(picks()).toHaveLength(4);
    const centreOf = (r: SVGRectElement): Point => [
      Number(r.getAttribute("x")) + Number(r.getAttribute("width")) / 2,
      Number(r.getAttribute("y")) + Number(r.getAttribute("height")) / 2,
    ];
    const ne = picks().find((r) => r.dataset.corner === "ne") as SVGRectElement;
    pointer(svg, "pointerdown", centreOf(ne));
    pointer(svg, "pointerup", centreOf(ne));
    await settle();
    expect(app.state.orienting).toEqual({ home: "ne" });
    expect(picks().map((r) => r.dataset.corner).sort()).toEqual(["nw", "se"]);
    expect(root.querySelector("rect.pick.chosen")).not.toBeNull();
  });

  it("does nothing else with a click while picking", async () => {
    const { app, fake, plate, svg } = await plateIn("nw-h");
    app.startOrienting();
    await settle();
    const from = toScreen(plate.view, CENTRE);
    pointer(svg, "pointerdown", from);
    pointer(svg, "pointermove", [from[0] + 40, from[1]]);
    pointer(svg, "pointerup", [from[0] + 40, from[1]]);
    await settle();
    expect(fake.called("piece_place")).toEqual([]);
    expect(app.state.orienting).toEqual({ home: null });
  });
});

describe("rp-plate: the pick shows every corner", () => {
  it("zooms out to the whole reach when the pick starts", async () => {
    const { app, root } = await plateIn("nw-h");
    app.requestView({ kind: "fit-paper" });
    await settle();
    app.startOrienting();
    await settle();
    const picks = Array.from(root.querySelectorAll("rect.pick")) as SVGRectElement[];
    expect(picks).toHaveLength(4);
    for (const r of picks) {
      const x = Number(r.getAttribute("x"));
      const y = Number(r.getAttribute("y"));
      expect(x >= 0 && x <= 800 && y >= 0 && y <= 600).toBe(true);
    }
  });
});
