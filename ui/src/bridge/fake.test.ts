import { describe, expect, it } from "vitest";
import { Client } from "./client";
import { FakeApi } from "./fake";

function setup() {
  const fake = new FakeApi();
  return { fake, client: new Client(fake) };
}

describe("FakeApi", () => {
  it("connects on a scan and needs Home before moving", async () => {
    const { client } = setup();
    expect((await client.call("plotter_scan")).machine.state).toBe("not_homed");
    await expect(client.call("plotter_jog", 10, 0)).rejects.toThrow("HOME label");
    await client.call("plotter_set_home");
    const moved = await client.call("plotter_jog", 10, 5);
    expect(moved.machine.position).toEqual([10, 5]);
    const far = (await client.call("plotter_goto", 5000, 5000)).machine.position ?? [0, 0];
    expect(far[0]).toBeCloseTo(863.108);
    expect(far[1]).toBeCloseTo(593.106);
  });

  it("reports a plotter whose model isn't known, and learns it", async () => {
    const { fake, client } = setup();
    fake.model = null;
    expect((await client.call("plotter_scan")).machine.state).toBe("needs_model");
    expect((await client.call("plotter_identify", 2, 1, "Lab")).machine.model_name).toBe("AxiDraw V3/A3 or SE/A3");
  });

  it("imports, places, lists and removes jobs", async () => {
    const { fake, client } = setup();
    const { job } = await client.call("job_import", "C:\\art\\site.svg", 0);
    expect(job).toMatchObject({ id: "job-1", name: "site", width_mm: 120, height_mm: 80 });
    const { piece } = await client.call("job_place", job.id, 6.35, 6.35);
    expect(piece.placement).toEqual({ x: 6.35, y: 6.35, scale: 1, scale_y: 1, rotation: 0 });
    expect((await client.call("job_colors")).colors.map((c) => c.name)).toEqual(["black", "red"]);
    expect((await client.call("job_remove", job.id)).removed_pieces).toEqual([piece.id]);
    expect(fake.called("job_remove")).toEqual([["job-1"]]);
    await expect(client.call("job_import", "C:\\art\\plan.afdesign", 0)).rejects.toThrow("In Affinity");
  });

  it("turns the paper and what's on it", async () => {
    const { client } = setup();
    const { job } = await client.call("job_import", "C:\\art\\site.svg", 0);
    await client.call("job_place", job.id, 10, 20);
    const reply = await client.call("paper_rotate");
    expect([reply.material.width, reply.material.height]).toEqual([215.9, 279.4]);
    expect(reply.paper.orientation).toBe("portrait");
    expect(reply.pieces[0].placement).toMatchObject({ x: 215.9 - 20 - 80, y: 10, rotation: 90 });
  });

  it("rotating custom paper flips its orientation", async () => {
    const fake = new FakeApi();
    await fake.material_set("custom", "landscape", 500, 300, 0, 0);
    const reply = await fake.paper_rotate();
    expect(reply.ok && reply.paper).toEqual({ size: "custom", orientation: "portrait", custom_width_mm: 300, custom_height_mm: 500 });
  });

  it("numbers only the visible pens", async () => {
    const { client } = setup();
    const { job } = await client.call("job_import", "C:\\art\\site.svg", 0);
    await client.call("job_place", job.id, 0, 0);
    await client.call("set_pen_visible", "#000000", false);
    const { colors } = await client.call("job_colors");
    expect(colors.map((c) => [c.layer, c.name, c.visible])).toEqual([
      [null, "black", false],
      [1, "red", true],
    ]);
  });
});

async function readyFake() {
  const fake = new FakeApi();
  const events: [string, unknown][] = [];
  fake.emit = (name, data) => events.push([name, data]);
  await fake.plotter_scan();
  await fake.plotter_set_home();
  await fake.job_import("C:\\Demo\\a.svg", 0);
  await fake.job_place("job-1", 10, 10);
  return { fake, events };
}

/** The plot and machine status (the fake's plot_status always replies ok). */
const plotStatus = (fake: FakeApi) => fake.plot_status();

const wait = () => new Promise((done) => setTimeout(done, 5));

describe("FakeApi plotting", () => {
  it("gives the Advanced options with their defaults, and the plot's state, at start", async () => {
    const reply = await new FakeApi().app_start();
    expect(reply.advanced_options.defaults).toMatchObject({ accel: 75, pen_up: null, hiding: false });
    expect(reply.settings.advanced).toEqual(reply.advanced_options.defaults);
    expect(reply.plot.state).toBe("idle");
  });

  it("prepares a plot with one layer per visible pen, in machine mm", async () => {
    const { fake } = await readyFake();
    const reply = await fake.plot_prepare();
    if (!reply.ok) throw new Error(reply.message);
    expect(reply.summary.layers.map((l) => l.name)).toEqual(["black", "red"]);
    expect(reply.summary.layers.map((l) => l.layer)).toEqual([1, 2]);
    const first = reply.summary.layers[0].path.find((run) => run.down);
    expect(first?.points.slice(0, 2)).toEqual([10, 10]); // the drawing's corner, from Home (paper at 0, 0)
    expect(reply.summary.total_seconds).toBeGreaterThan(0);
    expect(reply.summary.ink_bbox).toEqual([10, 10, 130, 90]);
  });

  it("asks for each pen, plots, and finishes at Home", async () => {
    const { fake, events } = await readyFake();
    await fake.plot_prepare();
    await fake.plot_start();
    expect((events.at(-1)?.[1] as { state: string }).state).toBe("load_pen");
    expect((await plotStatus(fake)).machine.state).toBe("plotting");
    await fake.plot_continue();
    fake.progress(0.5);
    expect(events.at(-1)?.[0]).toBe("plot_progress");
    fake.finishLayer();
    await fake.plot_continue();
    fake.finishLayer();
    const last = events.filter(([name]) => name === "plot_state").at(-1)?.[1] as { state: string; message: string };
    expect(last).toMatchObject({ state: "done", message: "Done! The pen is back Home." });
    expect((await plotStatus(fake)).machine).toMatchObject({ state: "ready", position: [0, 0] });
  });

  it("pauses at the next step, and cancels: the pen isn't Home, as in Python", async () => {
    const { fake } = await readyFake();
    await fake.set_pen_visible("#ff0000", false);
    await fake.plot_prepare();
    await fake.plot_start(); // one pen: plotting at once
    expect((await plotStatus(fake)).plot.state).toBe("plotting");
    await fake.plot_pause();
    expect((await plotStatus(fake)).plot.state).toBe("pausing");
    await wait();
    expect((await plotStatus(fake)).plot.state).toBe("paused");
    await fake.plot_cancel();
    const status = await plotStatus(fake);
    expect(status.plot).toMatchObject({ state: "ready", message: "Plot cancelled. Slide the pen Home before the next plot." });
    expect(status.machine.state).toBe("not_homed");
  });

  it("cancels at a pen change with the pen at Home", async () => {
    const { fake } = await readyFake();
    await fake.plot_prepare();
    await fake.plot_start();
    await fake.plot_cancel();
    const status = await plotStatus(fake);
    expect(status.plot).toMatchObject({ state: "ready", message: "Plot cancelled." });
    expect(status.machine.state).toBe("ready");
  });

  it("sends the pen Home while paused, then resumes", async () => {
    const { fake } = await readyFake();
    await fake.set_pen_visible("#ff0000", false);
    await fake.plot_prepare();
    await fake.plot_start();
    await fake.plot_pause();
    await wait();
    expect((await fake.plot_home()).ok).toBe(true);
    expect((await plotStatus(fake)).plot.state).toBe("homing");
    await wait();
    expect((await plotStatus(fake)).plot.state).toBe("paused_at_home");
    await fake.plot_resume();
    expect((await plotStatus(fake)).plot.state).toBe("plotting");
  });

  it("recovers from a pulled cable", async () => {
    const { fake } = await readyFake();
    await fake.set_pen_visible("#ff0000", false);
    await fake.plot_prepare();
    await fake.plot_start();
    fake.disconnect();
    expect((await plotStatus(fake)).plot).toMatchObject({ state: "reconnect", actions: ["reconnect", "cancel"] });
    await fake.plot_reconnect();
    expect((await plotStatus(fake)).plot.state).toBe("slide_home");
    await fake.plot_rehomed();
    expect((await plotStatus(fake)).plot.state).toBe("paused_at_home");
  });

  it("a change goes back to idle, and waits while plotting", async () => {
    const { fake } = await readyFake();
    await fake.plot_prepare();
    await fake.piece_place("piece-1", 20, 20, 1, 0, 1);
    expect((await plotStatus(fake)).plot.state).toBe("idle");
    await fake.plot_prepare();
    await fake.plot_start();
    await fake.plot_continue();
    await fake.set_pen_visible("#ff0000", false); // mid-plot: remembered until the plot ends
    expect((await plotStatus(fake)).plot.state).toBe("plotting");
    fake.finishLayer();
    await fake.plot_continue();
    fake.finishLayer();
    expect((await plotStatus(fake)).plot).toMatchObject({ state: "idle", message: "Done! The pen is back Home." });
  });

  it("Start and Trace wait for the plot to be prepared, and a change while preparing isn't lost", async () => {
    const { fake } = await readyFake();
    expect(await fake.plot_start()).toMatchObject({ ok: false, message: "Wait a moment: the plot is still being prepared." });
    const release = fake.hold("plot_prepare");
    const preparing = fake.plot_prepare();
    const still = "The plot is still being prepared. Wait a moment, then try again.";
    expect(await fake.plot_start()).toMatchObject({ ok: false, message: still });
    expect(await fake.plot_trace()).toMatchObject({ ok: false, message: still });
    expect(await fake.plot_prepare()).toMatchObject({ ok: false, message: still });
    await fake.piece_place("piece-1", 20, 20, 1, 0, 1);
    release();
    expect(await preparing).toMatchObject({
      ok: false,
      message: "Something changed while the plot was being prepared, so it's being prepared again.",
    });
    expect((await plotStatus(fake)).plot.state).toBe("idle");
    expect((await fake.plot_prepare()).ok).toBe(true);
  });

  it("refuses plotter moves and a paper turn mid-plot", async () => {
    const { fake } = await readyFake();
    await fake.plot_prepare();
    await fake.plot_start();
    const finish = "Finish or cancel the current plot first.";
    expect(await fake.plot_prepare()).toMatchObject({ ok: false, message: finish });
    expect(await fake.plot_start()).toMatchObject({ ok: false, message: finish });
    expect(await fake.paper_rotate()).toMatchObject({ ok: false, message: finish });
    expect(await fake.plotter_jog(5, 0)).toMatchObject({
      ok: false,
      message: "The plotter is in the middle of a plot. Finish or cancel the plot first.",
    });
    expect(await fake.plot_resume()).toMatchObject({ ok: false, message: "That can't be done right now." });
  });

  it("checks the power before each run", async () => {
    const { fake } = await readyFake();
    await fake.plot_prepare();
    await fake.plot_start();
    fake.powered = false;
    expect(await fake.plot_continue()).toMatchObject({
      ok: false,
      message: "The power adapter isn't plugged in. The pen can't move without it.",
    });
    expect((await plotStatus(fake)).plot.state).toBe("load_pen");
  });

  it("traces back to ready, and a Stop leaves the pen to be slid Home", async () => {
    const { fake, events } = await readyFake();
    await fake.plot_prepare();
    expect((await fake.plot_trace()).ok).toBe(true);
    const states = events.filter(([name]) => name === "plot_state").map(([, data]) => (data as { state: string }).state);
    expect(states.slice(-2)).toEqual(["tracing", "ready"]);
    const release = fake.hold("plot_trace");
    const tracing = fake.plot_trace();
    await fake.plotter_stop();
    release();
    expect(await tracing).toMatchObject({
      ok: false,
      message: "The plotter stopped before the move finished. Slide the pen Home, then click It's in the corner.",
    });
    const status = await plotStatus(fake);
    expect([status.machine.state, status.plot.state]).toEqual(["not_homed", "ready"]);
  });

  it("checks Advanced values as Python does, and keeps the rest", async () => {
    const fake = new FakeApi();
    expect(await fake.set_advanced({ accel: 101 })).toMatchObject({ ok: false, message: "Acceleration must be from 1 to 100." });
    expect(await fake.set_advanced({ reordering: 3 })).toMatchObject({ ok: false, message: "Path order must be one of 0, 1, 2, 4." });
    expect(await fake.set_advanced({ accel: 50.5 })).toMatchObject({ ok: false, message: "Acceleration must be a whole number." });
    expect(await fake.set_advanced({ hiding: 1 })).toMatchObject({ ok: false, message: "Hidden-line removal must be on or off." });
    expect(await fake.set_advanced({ pen_up: 35 })).toMatchObject({
      ok: false,
      message: "Pen-up height must be at least 10 above the pen-down height (30).",
    });
    expect(await fake.set_advanced({ bogus: 1 })).toMatchObject({ ok: false, message: "Unknown advanced option: bogus" });
    const reply = await fake.set_advanced({ accel: 40, pen_up: null });
    expect(reply.ok && reply.advanced).toMatchObject({ accel: 40, pen_up: null, speed_penup: 75 });
  });
});
