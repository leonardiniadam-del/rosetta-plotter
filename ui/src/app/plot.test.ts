import { describe, expect, it } from "vitest";
import { App } from "./app";
import { Client } from "../bridge/client";
import type { PlotStatus } from "../bridge/contract";
import { FakeApi } from "../bridge/fake";
import { initialState, Store } from "../state/store";
import { readyToPlot, settle, startApp } from "../test/setup";

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

  it("drops a prepare reply that a change overtook", async () => {
    const { app, fake } = await readyToPlot();
    const release = fake.hold("plot_prepare");
    await app.moveSelectionBy(10, 0);
    await settle();
    expect(app.state.preparing).toBe(true);
    const before = fake.called("plot_prepare").length;
    // Python says "ready", then a change sends it back to idle, and only then does the prepare's reply arrive.
    const emit = fake.emit;
    fake.emit = (name, data) => {
      emit(name, data);
      if (name === "plot_state" && (data as PlotStatus).state === "ready") {
        fake.emit = emit;
        emit("plot_state", { ...(data as PlotStatus), state: "idle" });
      }
    };
    release();
    const releaseNext = fake.hold("plot_prepare");
    await settle();
    expect(app.state.summary).toBeNull();
    expect(fake.called("plot_prepare").length).toBe(before + 1);
    releaseNext();
    await settle();
    expect(app.state.summary).not.toBeNull();
  });

  it("prepares again when asked while a prepare is running, even if that one fails quietly", async () => {
    const { app, fake } = await readyToPlot();
    const release = fake.hold("plot_prepare");
    await app.moveSelectionBy(10, 0);
    await settle();
    expect(app.state.preparing).toBe(true);
    const before = fake.called("plot_prepare").length;
    app.schedulePrepare(); // fires while the first prepare is still running
    await settle();
    fake.failNext("plot_prepare", "Nothing to plot: no lines land on the paper."); // no plot_state follows
    release();
    await settle();
    await settle();
    expect(fake.called("plot_prepare").length).toBe(before + 1);
    expect(app.state.summary).not.toBeNull();
    expect(app.state.prepareProblem).toBeNull();
  });

  it("prepares after a reload finds the plot already prepared in Python", async () => {
    const { fake } = await readyToPlot();
    const before = fake.called("plot_prepare").length;
    const app = new App(new Store(initialState()), new Client(fake), { colorsDelayMs: 0, prepareDelayMs: 0, scanIntervalMs: 60_000 });
    fake.emit = (name, data) => app.onEvent(name, data);
    await app.start();
    expect(app.state.plot.state).toBe("ready");
    await settle();
    await settle();
    expect(fake.called("plot_prepare").length).toBe(before + 1);
    expect(app.state.summary).not.toBeNull();
    await settle();
    expect(fake.called("plot_prepare").length).toBe(before + 1); // and only once
    app.stop();
  });

  it("stopping the App drops a prepare that was due again", async () => {
    const { app, fake } = await readyToPlot();
    const release = fake.hold("plot_prepare");
    await app.moveSelectionBy(10, 0);
    await settle();
    expect(app.state.preparing).toBe(true);
    const before = fake.called("plot_prepare").length;
    app.schedulePrepare(); // due again while the first is still running
    await settle();
    app.stop();
    release();
    await settle();
    await settle();
    expect(fake.called("plot_prepare").length).toBe(before);
  });

  it("keeps plot progress in its own store", async () => {
    const { app } = await readyToPlot();
    app.onEvent("plot_progress", { layer: 0, x: 5, y: 6, pendown_mm: 1, fraction: 0.1, seconds_left: 9 });
    expect(app.progress.state.value?.x).toBe(5);
  });
});

describe("plotting", () => {
  it("asks for each pen and finishes with Plot another copy", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    expect(app.state.plot.state).toBe("load_pen");
    await app.plotAction("continue");
    expect(app.state.plot.state).toBe("plotting");
    fake.finishLayer();
    await app.plotAction("continue");
    fake.finishLayer();
    await settle();
    expect(app.state.plot.state).toBe("done");
    expect(app.state.notice?.message).toBe("Done! The pen is back Home.");
    expect(app.state.notice?.actions?.map((a) => a.label)).toEqual(["Plot another copy"]);
    expect(app.state.machine.state).toBe("ready");
  });

  it("Plot another copy starts the plot again", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    await app.plotAction("continue");
    fake.finishLayer();
    await app.plotAction("continue");
    fake.finishLayer();
    await settle();
    app.state.notice?.actions?.[0].run();
    await settle();
    expect(fake.called("plot_start")).toHaveLength(2);
    expect(app.state.plot.state).toBe("load_pen");
    expect(app.state.notice).toBeNull();
  });

  it("explains instead of starting before Home", async () => {
    const { app, fake } = await startApp();
    await app.importFiles();
    await app.placeJob("job-1");
    await app.startPlot();
    expect(fake.called("plot_start")).toEqual([]);
    expect(app.state.notice?.message).toMatch(/^Home not set/);
  });

  it("Pause pauses the plot; Resume carries on", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    app.pause();
    await settle();
    expect(fake.called("plot_pause")).toHaveLength(1);
    expect(app.state.plot.state).toBe("paused");
    await app.plotAction("resume");
    expect(app.state.plot.state).toBe("plotting");
  });

  it("Stop asks, then pauses and cancels", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    expect(app.state.plot.state).toBe("plotting");
    app.stopPlot();
    expect(app.state.dialog).toMatchObject({ kind: "confirm", title: "Stop the plot?", confirm: "Stop", cancel: "Keep plotting" });
    const dialog = app.state.dialog;
    if (dialog?.kind === "confirm") dialog.run();
    await settle();
    await settle();
    expect(app.state.dialog).toBeNull();
    expect(fake.called("plot_pause")).toHaveLength(1);
    expect(fake.called("plot_cancel")).toHaveLength(1);
    expect(app.state.plot.state).toBe("ready");
    // Cancelled away from Home (as plotjob.py does): the pen's place is unknown, so Home must be set again.
    expect(app.state.notice?.message).toBe("Plot cancelled. Slide the pen Home before the next plot.");
    expect(app.state.machine.state).toBe("not_homed");
  });

  it("Cancel plot at a pen change keeps the plotter ready", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    expect(app.state.plot.state).toBe("load_pen");
    await app.plotAction("cancel");
    await settle();
    expect(fake.called("plot_cancel")).toHaveLength(1);
    expect(app.state.plot.state).toBe("ready");
    expect(app.state.notice?.message).toBe("Plot cancelled.");
    expect(app.state.machine.state).toBe("ready");
  });

  it("Stop during a trace stops the trace without asking", async () => {
    const { app, fake } = await readyToPlot();
    const release = fake.hold("plot_trace");
    void app.trace();
    await settle();
    expect(app.state.plot.state).toBe("tracing");
    app.stopPlot();
    expect(app.state.dialog).toBeNull();
    expect(fake.called("plotter_stop")).toHaveLength(1);
    release();
    await settle();
  });

  it("a pulled cable shows Continue and Cancel plot in the strip", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    fake.disconnect();
    expect(app.state.notice?.message).toBe("Plotter disconnected. Plug it back in, then click Continue.");
    expect(app.state.notice?.actions?.map((a) => a.label)).toEqual(["Continue", "Cancel plot"]);
    app.state.notice?.actions?.[0].run();
    await settle();
    expect(app.state.plot.state).toBe("slide_home");
    expect(app.state.notice?.actions?.map((a) => a.label)).toEqual(["It's in the corner", "Cancel plot"]);
    app.state.notice?.actions?.[0].run();
    await settle();
    expect(app.state.plot.state).toBe("paused_at_home");
    expect(app.state.notice).toBeNull();
  });

  it("a refused plot action shows why and asks Python where the plot is", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    fake.powered = false; // run actions check the power, as Python does
    const statusBefore = fake.called("plot_status").length;
    expect(await app.plotAction("continue")).toBe(false);
    expect(app.state.notice?.message).toBe("The power adapter isn't plugged in. The pen can't move without it.");
    expect(fake.called("plot_status").length).toBe(statusBefore + 1);
    expect(app.state.plot.state).toBe("load_pen");
  });

  it("closing mid-plot asks first", async () => {
    const { app, fake } = await readyToPlot();
    app.onEvent("close_requested", {});
    expect(app.state.dialog).toMatchObject({ kind: "confirm", title: "Stop the plot and close Rosetta Plotter?", confirm: "Stop and close" });
    const dialog = app.state.dialog;
    if (dialog?.kind === "confirm") dialog.run();
    await settle();
    expect(fake.called("quit_confirmed")).toHaveLength(1);
  });
});
