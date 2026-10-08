import { describe, expect, it } from "vitest";
import { settle, startApp } from "../test/setup";

async function withOneJob() {
  const started = await startApp();
  await started.app.importFiles();
  await started.app.placeJob("job-1"); // 120 x 80 mm at the margin corner
  return started;
}

describe("App", () => {
  it("starts with Python's state and finds the plotter", async () => {
    const { app, fake } = await startApp();
    expect(app.state.ready).toBe(true);
    expect(app.state.machine.state).toBe("not_homed");
    expect(fake.called("plotter_scan")).toHaveLength(1);
  });

  it("sets Home in two clicks", async () => {
    const { app, fake } = await startApp();
    await app.setHome();
    expect(app.state.homing).toBe(true);
    expect(fake.called("plotter_motors_off")).toHaveLength(1);
    await app.setHome();
    expect([app.state.homing, app.state.machine.state]).toEqual([false, "ready"]);
  });

  it("explains instead of moving before Home", async () => {
    const { app, fake } = await startApp();
    await app.jog(1, 0);
    expect(fake.called("plotter_jog")).toEqual([]);
    expect(app.state.notice?.message).toMatch(/^Home not set/);
  });

  it("jogs by the chosen step", async () => {
    const { app, fake } = await startApp();
    await app.setHome();
    await app.setHome();
    app.setJogStep(10);
    await app.jog(0, 1);
    expect(fake.called("plotter_jog")).toEqual([[0, 10]]);
    expect(app.state.machine.position).toEqual([0, 10]);
  });

  it("imports into the Jobs list and places a job at the margin corner", async () => {
    const { app, fake } = await startApp();
    await app.importFiles();
    expect(app.state.jobs.map((j) => j.name)).toEqual(["site-plan"]);
    expect(app.state.pieces).toEqual([]);
    await app.placeJob("job-1");
    expect(fake.called("job_place")).toEqual([["job-1", 6.35, 6.35]]);
    expect(app.state.selection).toEqual(["piece-1"]);
    await settle();
    expect(app.state.colors.map((c) => c.name)).toEqual(["black", "red"]);
  });

  it("asks which page of a many-page PDF", async () => {
    const { app, fake } = await startApp();
    const done = app.importFiles(["C:\\docs\\set.pdf"]);
    await settle();
    const dialog = app.state.dialog;
    expect(dialog?.kind).toBe("pages");
    if (dialog?.kind === "pages") dialog.resolve(2);
    await done;
    expect(fake.called("job_import")).toEqual([["C:\\docs\\set.pdf", 2]]);
    expect(app.state.dialog).toBeNull();
  });

  it("places files dropped from Windows where they were dropped", async () => {
    const { app, fake } = await startApp();
    app.lastFileDrop = { point: [40, 30], at: Date.now() };
    app.onEvent("files_dropped", { paths: ["C:\\art\\a.svg"] });
    await settle();
    expect(fake.called("job_place")).toEqual([["job-1", 40, 30]]);
  });

  it("asks before removing a job that has copies on the paper", async () => {
    const { app, fake } = await withOneJob();
    await app.placeJob("job-1");
    app.removeJob("job-1");
    expect(app.state.notice?.message).toBe("Remove site-plan and its 2 copies on the paper?");
    app.state.notice?.actions?.[0].run();
    await settle();
    expect(fake.called("job_remove")).toEqual([["job-1"]]);
    expect([app.state.jobs, app.state.pieces, app.state.selection]).toEqual([[], [], []]);
  });

  it("resizes linked or stretched, and explains a turned stretch", async () => {
    const { app } = await withOneJob();
    await app.resizeSelected({ width: 240 });
    expect(app.state.pieces[0].placement).toMatchObject({ scale: 2, scale_y: 2 });
    app.toggleLink();
    await app.resizeSelected({ height: 80 });
    expect(app.state.pieces[0].placement).toMatchObject({ scale: 2, scale_y: 1 });
    await app.rotateSelectedTo(30);
    await app.resizeSelected({ width: 100 });
    expect(app.state.notice?.message).toBe("Use W% and H% to stretch a turned drawing.");
  });

  it("turns a drawing about its center", async () => {
    const { app, fake } = await withOneJob();
    await app.rotateSelectedTo(90);
    // 120 x 80 at (6.35, 6.35) becomes 80 x 120 about the same center.
    const [id, x, y, scale, rotation, scaleY] = fake.called("piece_place").at(-1) as number[];
    expect(id).toBe("piece-1");
    expect(x).toBeCloseTo(26.35);
    expect(y).toBeCloseTo(-13.65);
    expect([scale, rotation, scaleY]).toEqual([1, 90, 1]);
  });

  it("nudges, centers and fits", async () => {
    const { app } = await withOneJob();
    await app.moveSelectionBy(1, -1);
    expect(app.state.pieces[0].placement.x).toBeCloseTo(7.35);
    expect(app.state.pieces[0].placement.y).toBeCloseTo(5.35);
    await app.centerSelection();
    expect(app.state.pieces[0].placement.x).toBeCloseTo((279.4 - 120) / 2);
    await app.setScale(4, 4);
    await app.fitSelection();
    const p = app.state.pieces[0].placement;
    expect(p.scale).toBeCloseTo((279.4 - 2 * 6.35) / 120);
    expect(p.scale_y).toBeCloseTo(p.scale);
  });

  it("quick nudges all land, in order, and a late reply never undoes a newer one", async () => {
    const { app, fake } = await withOneJob();
    const release = fake.hold("piece_place");
    void app.moveSelectionBy(1, 0);
    void app.moveSelectionBy(1, 0);
    void app.moveSelectionBy(1, 0);
    await settle();
    expect(app.state.pieces[0].placement.x).toBeCloseTo(9.35);
    release();
    await settle();
    const sent = fake.called("piece_place").map((args) => args[1] as number);
    expect(sent.at(-1)).toBeCloseTo(9.35);
    expect(sent.length).toBeLessThan(3); // nudges made while one is on its way are sent as one
    expect(app.state.pieces[0].placement.x).toBeCloseTo(9.35);
    const { pieces } = await fake.job_list();
    expect(pieces[0].placement.x).toBeCloseTo(9.35);
  });

  it("puts a drawing back when Python refuses the change", async () => {
    const { app, fake } = await withOneJob();
    fake.failNext("piece_place", "Nope.");
    await app.setPlacement("piece-1", { ...app.state.pieces[0].placement, x: 50 });
    await settle();
    expect(app.state.pieces[0].placement.x).toBeCloseTo(6.35);
    expect(app.state.notice?.message).toBe("Nope.");
  });

  it("refuses to scale past 10000% without asking Python", async () => {
    const { app, fake } = await withOneJob();
    await app.setScale(150, 150);
    await settle();
    expect(fake.called("piece_place")).toEqual([]);
    expect(app.state.pieces[0].placement.scale).toBe(1);
    expect(app.state.notice?.message).toBe("Drawings can be scaled up to 10000%.");
  });

  it("turns the paper with everything on it", async () => {
    const { app } = await withOneJob();
    await app.rotatePaper();
    expect([app.state.material.width, app.state.paper.orientation, app.state.pieces[0].placement.rotation]).toEqual([
      215.9,
      "portrait",
      90,
    ]);
  });

  it("skips a pen color", async () => {
    const { app, fake } = await withOneJob();
    await settle();
    await app.setPenVisible("#ff0000", false);
    await settle();
    expect(fake.called("set_pen_visible")).toEqual([["#ff0000", false]]);
    expect(app.state.colors.find((c) => c.color === "#ff0000")?.visible).toBe(false);
  });

  it("shows Python's problems in the strip", async () => {
    const { app } = await startApp();
    await app.importFiles(["C:\\art\\plan.afdesign"]);
    expect(app.state.notice).toMatchObject({ kind: "error" });
    expect(app.state.notice?.message).toContain("In Affinity");
  });

  it("refreshes the pen colors after the paper changes", async () => {
    const { app, fake } = await withOneJob();
    await settle();
    const before = fake.called("job_colors").length;
    await app.setPaper("a4", "landscape");
    await settle();
    expect(fake.called("job_colors").length).toBeGreaterThan(before);
  });

  it("names the plotter by its stored label, and says if the plotter shortened it", async () => {
    const { app } = await startApp();
    await app.identify(5, 1, "PSU Lab");
    expect(app.state.notice?.message).toBe('Saved. This plotter is now named "PSU Lab".');
    await app.identify(5, 1, "Portland State Univ.");
    expect(app.state.notice?.message).toBe('Saved. This plotter is now named "Portland State U" (the plotter keeps a shorter name).');
  });

  it("says once when the plotter's firmware is old", async () => {
    const { app, fake } = await startApp();
    fake.oldFirmware = true;
    await app.scan();
    await app.scan();
    expect(app.state.notice?.message).toBe("This plotter's firmware is old. You'll be asked for the model on each laptop.");
    app.dismissNotice();
    await app.scan();
    expect(app.state.notice).toBeNull();
  });

  it("checks the margin in the student's units before asking Python", async () => {
    const { app, fake } = await startApp();
    await app.setMargin(60);
    expect(fake.called("set_margin")).toEqual([]);
    expect(app.state.notice?.message).toBe("The margin must be from 0 to 1.97 in.");
  });

  it("accepts the margin limit typed as it's shown (1.97 in)", async () => {
    const { app, fake } = await startApp();
    await app.setMargin(1.97 * 25.4);
    expect(fake.called("set_margin")).toEqual([[50]]);
    expect(app.state.margin).toBe(50);
  });

  it("checks a custom paper size before asking Python", async () => {
    const { app, fake } = await startApp();
    await app.setUnits("cm");
    await app.setPaper("custom", "landscape", 2500, 300);
    expect(fake.called("material_set")).toEqual([]);
    expect(app.state.notice?.message).toBe("Paper width and height must be above 0 and at most 200.00 cm.");
  });

  it("falls back to a dialog when the clipboard is unavailable", async () => {
    const { app } = await startApp();
    await app.copyDiagnostics();
    expect(app.state.dialog).toMatchObject({ kind: "text", title: "Diagnostics" });
  });
});
