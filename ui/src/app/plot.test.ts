import { describe, expect, it, vi } from "vitest";
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
    expect(app.state.notice?.kind).toBe("warning"); // stays until the student has read it
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
    expect(app.state.notice).toMatchObject({ message: "Lifting the pen and closing…", keep: true });
    expect(app.state.notice?.actions).toBeUndefined();
    await settle();
    expect(fake.called("quit_confirmed")).toHaveLength(1);
  });

  it("a refused recovery step keeps its buttons, with the reason", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    fake.disconnect();
    fake.plot_reconnect = async () => ({ ok: false, message: "Still no plotter found.", details: "USB error 5" });
    app.state.notice?.actions?.[0].run();
    await settle();
    expect(app.state.plot.state).toBe("reconnect");
    expect(app.state.notice).toMatchObject({ kind: "warning", message: "Still no plotter found.", details: "USB error 5", source: "plot" });
    expect(app.state.notice?.actions?.map((a) => a.label)).toEqual(["Continue", "Cancel plot"]);
  });

  it("Stop cancels at a pen change when the pen finishes as the pause arrives", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    await app.plotAction("continue");
    const pause = fake.plot_pause.bind(fake);
    fake.plot_pause = async () => {
      fake.finishLayer(); // now asking for the red pen
      return pause();
    };
    app.stopPlot();
    const dialog = app.state.dialog;
    if (dialog?.kind === "confirm") dialog.run();
    await settle();
    await settle();
    expect(fake.called("plot_cancel")).toHaveLength(1);
    expect(app.state.plot.state).toBe("ready");
    expect(app.state.notice?.message).toBe("Plot cancelled.");
  });

  it("Stop cancels when the cable is pulled while pausing", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    const pause = fake.plot_pause.bind(fake);
    fake.plot_pause = async () => {
      const reply = await pause(); // "pausing"
      fake.disconnect(); // the event overtakes the reply
      return reply;
    };
    app.stopPlot();
    const dialog = app.state.dialog;
    if (dialog?.kind === "confirm") dialog.run();
    await settle();
    await settle();
    expect(fake.called("plot_cancel")).toHaveLength(1);
    expect(app.state.plot.state).toBe("ready");
    expect(app.state.notice?.message).toBe("Plot cancelled. Slide the pen Home before the next plot.");
  });

  it("a reply older than the newest plot_state event doesn't undo it", async () => {
    const { app, fake } = await readyToPlot();
    const start = fake.plot_start.bind(fake);
    fake.plot_start = async () => {
      const reply = await start(); // "load_pen"
      if (reply.ok) {
        fake.emit("plot_state", { ...reply.plot, state: "not_connected", actions: ["retry", "cancel"], message: "Lost the plotter." });
      }
      return reply;
    };
    await app.startPlot();
    expect(app.state.plot.state).toBe("not_connected");
    expect(app.state.notice?.actions?.map((a) => a.label)).toEqual(["Retry", "Cancel plot"]);
  });
});

describe("notices", () => {
  it("only info notices without buttons close by themselves", async () => {
    const { app } = await startApp();
    vi.useFakeTimers();
    try {
      app.notify({ kind: "info", message: "Done! The pen is back Home.", actions: [{ label: "Plot another copy", run: () => {} }] });
      vi.advanceTimersByTime(60_000);
      expect(app.state.notice?.message).toBe("Done! The pen is back Home.");
      app.notify({ kind: "info", message: "Lifting the pen and closing…", keep: true });
      vi.advanceTimersByTime(60_000);
      expect(app.state.notice?.message).toBe("Lifting the pen and closing…");
      app.notify({ kind: "info", message: "Saved." });
      vi.advanceTimersByTime(60_000);
      expect(app.state.notice).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("plot actions and their confirmations", () => {
  it("a Stop question closes when the plot moves on", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    await app.plotAction("continue");
    expect(app.state.plot.state).toBe("plotting");
    app.stopPlot();
    expect(app.state.dialog?.kind).toBe("confirm");
    fake.finishLayer(); // the pen finished while the question was open: now the pen change asks
    await settle();
    expect(app.state.plot.state).toBe("load_pen");
    await app.plotAction("cancel");
    await settle();
    expect(app.state.plot.state).toBe("ready");
    expect(app.state.dialog).toBeNull();
  });

  it("a Cancel plot question closes when the plot ends", async () => {
    const { app } = await readyToPlot();
    await app.startPlot();
    app.cancelPlot();
    expect(app.state.dialog?.kind).toBe("confirm");
    await app.plotAction("cancel");
    await settle();
    expect(app.state.dialog).toBeNull();
  });

  it("the close-the-window question stays when the plot is at rest", async () => {
    const { app } = await readyToPlot();
    app.onEvent("close_requested", {});
    expect(app.state.dialog?.kind).toBe("confirm");
    await app.refreshPlot();
    expect(app.state.dialog?.kind).toBe("confirm");
  });

  it("a second click on an action already on its way is ignored", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    const first = app.plotAction("continue");
    const second = app.plotAction("continue");
    expect(await second).toBe(false);
    await first;
    await settle();
    expect(fake.called("plot_continue")).toHaveLength(1);
    expect(app.state.notice?.kind).not.toBe("error");
  });
});

