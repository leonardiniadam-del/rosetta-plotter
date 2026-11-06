import { describe, expect, it } from "vitest";
import { handleShortcut } from "../shortcuts";
import { readyToPlot, settle, startApp } from "../test/setup";

describe("plate orientation", () => {
  it("starts in the saved orientation and changes it", async () => {
    const { app, fake } = await startApp();
    expect(app.state.orientation).toBe("nw-h");
    await app.setPlotterOrientation("se-v");
    expect(app.state.orientation).toBe("se-v");
    expect(fake.called("set_orientation")).toEqual([["se-v"]]);
  });

  it("starts from what Python saved", async () => {
    const fake = (await startApp()).fake;
    fake.orientation = "sw-h";
    const { app } = await startApp(fake);
    expect(app.state.orientation).toBe("sw-h");
  });

  it("takes the plotter's orientation when it is found", async () => {
    const { app, fake } = await startApp();
    fake.orientation = "ne-h"; // as if this plotter's saved view came back
    await app.scan();
    expect(app.state.orientation).toBe("ne-h");
  });

  it("won't change orientation during a plot", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    await app.setPlotterOrientation("sw-h");
    expect(fake.called("set_orientation")).toEqual([]);
    expect(app.state.orientation).toBe("nw-h");
    expect(app.state.notice?.message).toBe("A plot is running.");
  });

  it("goes back if Python refuses", async () => {
    const { app } = await startApp();
    await app.setPlotterOrientation("up" as never);
    expect(app.state.orientation).toBe("nw-h");
    expect(app.state.notice?.kind).toBe("error");
  });
});

describe("moving in screen directions", () => {
  it("jogs the way the screen shows", async () => {
    const { app, fake } = await startApp();
    await app.setHome();
    await app.setHome();
    await app.setPlotterOrientation("ne-v"); // +X down, +Y left
    await app.jog(0, 1); // screen down
    expect(fake.called("plotter_jog")).toEqual([[1, 0]]);
    await app.jog(1, 0); // screen right = machine -Y
    expect(fake.called("plotter_jog").at(-1)).toEqual([0, -1]);
  });

  it("nudges a drawing the way the screen shows", async () => {
    const { app, fake } = await startApp();
    await app.importFiles();
    await app.placeJob("job-1");
    await app.setPlotterOrientation("se-h"); // +X left
    handleShortcut(app, new KeyboardEvent("keydown", { key: "ArrowRight" }));
    await settle();
    const [, x, y] = fake.called("piece_place").at(-1) as [string, number, number];
    expect([x, y]).toEqual([6.35 - 1, 6.35]);
  });
});

describe("Set plotter orientation: two picks", () => {
  it("asks for HOME's corner, then the X corner, then turns the plate", async () => {
    const { app, fake } = await startApp();
    app.startOrienting();
    expect(app.state.orienting).toEqual({ home: null });
    expect(app.state.notice?.message).toBe("Click the corner where HOME is on your plotter, as you face it.");
    await app.pickCorner("ne");
    expect(app.state.orienting).toEqual({ home: "ne" });
    expect(app.state.notice?.message).toBe("Click the corner the pen moves toward along X (along the rail).");
    await app.pickCorner("se");
    expect(fake.called("set_orientation")).toEqual([["ne-v"]]);
    expect(app.state.orienting).toBeNull();
    expect(app.state.notice).toBeNull();
  });

  it("ignores a second corner that doesn't share an edge with HOME's", async () => {
    const { app, fake } = await startApp();
    app.startOrienting();
    await app.pickCorner("nw");
    await app.pickCorner("se");
    expect(fake.called("set_orientation")).toEqual([]);
    expect(app.state.orienting).toEqual({ home: "nw" });
  });

  it("Esc cancels the pick before it cancels Set Home", async () => {
    const { app } = await startApp();
    await app.setHome(); // homing: the motors are off
    app.startOrienting();
    handleShortcut(app, new KeyboardEvent("keydown", { key: "Escape" }));
    expect(app.state.orienting).toBeNull();
    expect(app.state.notice).toBeNull();
    expect(app.state.homing).toBe(true);
  });

  it("can't start during a plot", async () => {
    const { app } = await readyToPlot();
    await app.startPlot();
    app.startOrienting();
    expect(app.state.orienting).toBeNull();
    expect(app.state.notice?.message).toBe("A plot is running.");
  });

  it("Reset goes back to the standard view", async () => {
    const { app, fake } = await startApp();
    await app.setPlotterOrientation("sw-h");
    await app.resetOrientation();
    expect(fake.called("set_orientation").at(-1)).toEqual(["nw-h"]);
  });
});
