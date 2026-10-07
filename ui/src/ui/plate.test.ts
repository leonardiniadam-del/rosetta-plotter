import { describe, expect, it } from "vitest";
import "./plate";
import { JOB_MIME } from "../canvas/interaction";
import { mount, settle, shadow, startApp } from "../test/setup";
import type { RpPlate } from "./plate";

async function plateWithJob() {
  const started = await startApp();
  await started.app.importFiles();
  await started.app.placeJob("job-1"); // 120 x 80 at (6.35, 6.35)
  const plate = await mount<RpPlate>("rp-plate");
  await settle();
  return { ...started, plate, root: shadow(plate), svg: shadow(plate).querySelector("svg") as SVGSVGElement };
}

function pointer(svg: Element, type: string, x: number, y: number, extra: MouseEventInit = {}) {
  svg.dispatchEvent(new MouseEvent(type, { clientX: x, clientY: y, button: 0, bubbles: true, ...extra }));
}

async function drag(svg: Element, from: [number, number], to: [number, number], extra: MouseEventInit = {}) {
  pointer(svg, "pointerdown", ...from, extra);
  pointer(svg, "pointermove", ...to, extra);
  pointer(svg, "pointerup", ...to, extra);
  await settle();
}

describe("rp-plate", () => {
  it("draws the paper, the reach, the grid and the drawings, with no text", async () => {
    const { app, root } = await plateWithJob();
    expect(root.querySelector("rect.paper")).not.toBeNull();
    expect(root.querySelector("rect.reach")).not.toBeNull();
    expect(root.querySelectorAll("line.minor").length).toBeGreaterThan(0);
    expect(root.querySelectorAll("path.ink")).toHaveLength(2);
    expect(root.querySelectorAll("path.off")).toHaveLength(2);
    expect(root.querySelector("text")).toBeNull();
    app.toggleView("grid");
    await settle();
    expect(root.querySelectorAll("line.minor")).toHaveLength(0);
  });

  it("fades a hidden pen", async () => {
    const { app, root } = await plateWithJob();
    await app.setPenVisible("#ff0000", false);
    await settle();
    expect(root.querySelectorAll("path.ink.hidden")).toHaveLength(1);
  });

  it("shows the pen once Home is set", async () => {
    const { app, root } = await plateWithJob();
    expect(root.querySelector(".cross-box")).toBeNull();
    await app.setHome();
    await app.setHome();
    await settle();
    expect(root.querySelector(".cross-box")).not.toBeNull();
  });

  it("drags a drawing", async () => {
    const { fake, svg } = await plateWithJob();
    await drag(svg, [50, 50], [60, 70]);
    const [id, x, y] = fake.called("piece_place").at(-1) as [string, number, number];
    expect(id).toBe("piece-1");
    expect(x).toBeCloseTo(16.35);
    expect(y).toBeCloseTo(26.35);
  });

  it("stretches with a corner handle, or keeps proportions with Shift", async () => {
    const { fake, svg } = await plateWithJob();
    await drag(svg, [126.35, 86.35], [246.35, 86.35]);
    expect(fake.called("piece_place").at(-1)?.slice(3)).toEqual([2, 0, 1]);
    await drag(svg, [246.35, 86.35], [246.35, 166.35], { shiftKey: true });
    const [, , , scale, , scaleY] = fake.called("piece_place").at(-1) as number[];
    expect(scale).toBeCloseTo(scaleY * 2);
  });

  it("sends nothing for a click that doesn't move, resize or turn", async () => {
    const { app, fake, svg } = await plateWithJob();
    pointer(svg, "pointerdown", 50, 50);
    pointer(svg, "pointerup", 50, 50);
    pointer(svg, "pointerdown", 126.35, 86.35);
    pointer(svg, "pointerup", 126.35, 86.35);
    app.setTool("rotate");
    await settle();
    pointer(svg, "pointerdown", 166.35, 46.35);
    pointer(svg, "pointerup", 166.35, 46.35);
    await settle();
    expect(fake.called("piece_place")).toEqual([]);
  });

  it("keeps the drawings still while a plot runs", async () => {
    const { app, fake, root, svg } = await plateWithJob();
    app.onEvent("plot_state", { ...app.state.plot, state: "plotting" });
    await settle();
    expect(root.querySelectorAll("rect.handle")).toHaveLength(0);
    await drag(svg, [50, 50], [60, 70]);
    await drag(svg, [126.35, 86.35], [246.35, 86.35]);
    expect(fake.called("piece_place")).toEqual([]);
    expect(app.state.pieces[0].placement).toMatchObject({ x: 6.35, y: 6.35, scale: 1, scale_y: 1 });
  });

  it("turns with the Rotate tool, snapping with Shift", async () => {
    const { app, fake, svg } = await plateWithJob();
    app.setTool("rotate");
    await settle();
    // Center is (66.35, 46.35): from straight right of it to straight below it is a quarter turn.
    await drag(svg, [166.35, 46.35], [70, 146.35], { shiftKey: true });
    expect(fake.called("piece_place").at(-1)?.[4]).toBe(90);
  });

  it("selects with a marquee and clears on an empty click", async () => {
    const { app, svg } = await plateWithJob();
    await drag(svg, [500, 500], [505, 505]);
    expect(app.state.selection).toEqual([]);
    await drag(svg, [0, 0], [200, 200]);
    expect(app.state.selection).toEqual(["piece-1"]);
  });

  it("places a job dropped from the Jobs list", async () => {
    const { fake, svg } = await plateWithJob();
    const drop = new Event("drop", { bubbles: true, cancelable: true });
    Object.defineProperties(drop, {
      clientX: { value: 100 },
      clientY: { value: 50 },
      dataTransfer: { value: { types: [JOB_MIME], getData: () => "job-1" } },
    });
    svg.dispatchEvent(drop);
    await settle();
    expect(fake.called("job_place").at(-1)).toEqual(["job-1", 100, 50]);
  });

  it("zooms with the wheel", async () => {
    const { plate, svg } = await plateWithJob();
    svg.dispatchEvent(new WheelEvent("wheel", { deltaY: -200, clientX: 10, clientY: 10, bubbles: true, cancelable: true }));
    expect(plate.view.scale).toBeGreaterThan(1);
  });

  it("explains instead of moving the pen before Home", async () => {
    const { app, fake, svg } = await plateWithJob();
    app.setTool("pen");
    await settle();
    pointer(svg, "pointerdown", 30, 30);
    await settle();
    expect(fake.called("plotter_goto")).toEqual([]);
    expect(app.state.notice?.message).toMatch(/^Home not set/);
  });
});
