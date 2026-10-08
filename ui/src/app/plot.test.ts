import { describe, expect, it } from "vitest";
import { App } from "./app";
import { Client } from "../bridge/client";
import { FakeApi } from "../bridge/fake";
import { initialState, Store } from "../state/store";
import { readyToPlot, settle } from "../test/setup";

describe("preparing the plot", () => {
  it("prepares once something is placed, and shows the times", async () => {
    const { app, fake } = await readyToPlot();
    expect(fake.called("plot_prepare").length).toBeGreaterThanOrEqual(1);
    expect(app.state.summary?.layers.map((l) => l.name)).toEqual(["black", "red"]);
    expect(app.state.plot.state).toBe("ready");
  });

  it("prepares again after a change", async () => {
    const { app, fake } = await readyToPlot();
    const before = fake.called("plot_prepare").length;
    await app.moveSelectionBy(10, 0);
    expect(app.state.summary).toBeNull();
    await settle();
    await settle();
    expect(fake.called("plot_prepare").length).toBe(before + 1);
    expect(app.state.summary).not.toBeNull();
  });

  it("never prepares without a model", async () => {
    const fake = new FakeApi();
    fake.model = null;
    const app = new App(new Store(initialState()), new Client(fake), { colorsDelayMs: 0, prepareDelayMs: 0, scanIntervalMs: 60_000 });
    fake.emit = (name, data) => app.onEvent(name, data);
    await app.start();
    await app.importFiles();
    await app.placeJob("job-1");
    await settle();
    expect(fake.called("plot_prepare")).toEqual([]);
    app.stop();
  });

  it("shows a prepare problem on Start, quietly", async () => {
    const fake = new FakeApi();
    fake.failNext("plot_prepare", "Nothing to plot: no lines land on the paper.");
    const { app } = await readyToPlot(fake);
    expect(app.state.prepareProblem).toBe("Nothing to plot: no lines land on the paper.");
    expect(app.state.notice).toBeNull();
  });

  it("keeps plot progress in its own store", async () => {
    const { app } = await readyToPlot();
    app.onEvent("plot_progress", { layer: 0, x: 5, y: 6, pendown_mm: 1, fraction: 0.1, seconds_left: 9 });
    expect(app.progress.state.value?.x).toBe(5);
  });
});
