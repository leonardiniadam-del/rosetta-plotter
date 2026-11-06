import { describe, expect, it } from "vitest";
import { readyToPlot, startApp } from "../test/setup";

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
