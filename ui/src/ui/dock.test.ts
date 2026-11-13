import { describe, expect, it, vi } from "vitest";
import "./dock";
import { mount, settle, shadow, readyToPlot, startApp } from "../test/setup";

function labelled(root: ShadowRoot, label: string): HTMLElement {
  const found = root.querySelector(`[aria-label^="${label}"]`);
  if (!found) throw new Error(`nothing labelled ${label}`);
  return found as HTMLElement;
}

describe("Jobs panel", () => {
  it("imports, places by double-click and marks what's placed", async () => {
    const { fake } = await startApp();
    const root = shadow(await mount("rp-jobs"));
    expect(root.textContent).toContain("Import SVG, PDF or AI files");
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.includes("Import")) as HTMLButtonElement).click();
    await settle();
    const row = root.querySelector(".row") as HTMLElement;
    expect(row.textContent).toContain("site-plan");
    row.dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
    await settle();
    expect(fake.called("job_place")).toEqual([["job-1", 6.35, 6.35]]);
    expect(root.querySelector(".check")).not.toBeNull();
  });

  it("offers Place, Remove and Show issues on right-click", async () => {
    const { app, fake } = await startApp();
    await app.importFiles();
    const root = shadow(await mount("rp-jobs"));
    root.querySelector(".row")?.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 5, clientY: 5 }));
    await settle();
    (Array.from(root.querySelectorAll('[role="menuitem"]')).find((b) => b.textContent === "Remove from list") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("job_remove")).toEqual([["job-1"]]); // no copies, so no question
  });

  it("Show issues explains when a file has none", async () => {
    const { app } = await startApp();
    await app.importFiles();
    const root = shadow(await mount("rp-jobs"));
    root.querySelector(".row")?.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 5, clientY: 5 }));
    await settle();
    const show = Array.from(root.querySelectorAll('[role="menuitem"]')).find((b) => b.textContent === "Show issues") as HTMLButtonElement;
    expect([show.disabled, show.getAttribute("aria-disabled")]).toEqual([false, "true"]);
    show.click();
    await settle();
    expect(app.state.notice?.message).toBe("This file has no issues.");
  });

  it("Delete on a focused job row removes it", async () => {
    const { app } = await startApp();
    await app.importFiles();
    const jobs = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-jobs");
    await jobs.updateComplete;
    const row = shadow(jobs).querySelector(".row") as HTMLElement;
    row.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));
    await settle();
    expect(app.state.jobs).toEqual([]);
  });
});

describe("Pens panel", () => {
  it("lists pens and skips one with the eye", async () => {
    const { app, fake } = await startApp();
    await app.importFiles();
    await app.placeJob("job-1");
    await settle();
    const root = shadow(await mount("rp-pens"));
    expect(root.textContent).toContain("1 Black");
    expect(root.textContent).toContain("2 Red");
    labelled(root, "Plot the red pen").click();
    await settle();
    expect(fake.called("set_pen_visible")).toEqual([["#ff0000", false]]);
    expect(root.textContent).toContain("– Red");
    // The eye keeps its name; aria-pressed says whether the pen is plotted.
    expect(labelled(root, "Plot the red pen").getAttribute("aria-pressed")).toBe("false");
  });
});

describe("Plotter panel", () => {
  it("jogs once Home is set, by the chosen step", async () => {
    const { app, fake } = await startApp();
    const root = shadow(await mount("rp-plotter"));
    expect(labelled(root, "Move pen right").getAttribute("aria-disabled")).toBe("true");
    await app.setHome();
    await app.setHome();
    await settle();
    labelled(root, "Move pen right").click();
    await settle();
    labelled(root, "Step 10 mm").click();
    await settle();
    labelled(root, "Move pen down (on screen)").click();
    await settle();
    labelled(root, "Step 0.1 mm").click();
    await settle();
    labelled(root, "Move pen left (on screen)").click();
    await settle();
    expect(fake.called("plotter_jog")).toEqual([[1, 0], [0, 10], [-0.1, 0]]);
  });

  it("offers sub-millimetre to 100 mm steps", async () => {
    await startApp();
    const root = shadow(await mount("rp-plotter"));
    const steps = Array.from(root.querySelectorAll(".steps button")).map((b) => b.textContent?.trim());
    expect(steps).toEqual(["0.1", "0.5", "1", "10", "50", "100"]);
  });

  it("sends the pen Home from the middle of the jog pad", async () => {
    const { app, fake } = await startApp();
    const root = shadow(await mount("rp-plotter"));
    await app.setHome();
    await app.setHome();
    await settle();
    labelled(root, "Send the pen Home").click();
    await settle();
    expect(fake.called("plotter_goto")).toEqual([[0, 0]]);
  });

  it("raises and lowers the pen before Home is set", async () => {
    const { fake } = await startApp();
    const root = shadow(await mount("rp-plotter"));
    const press = (text: string) => (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === text) as HTMLButtonElement).click();
    press("Pen down");
    await settle();
    press("Pen up");
    await settle();
    expect(fake.called("plotter_pen")).toEqual([[true], [false]]);
  });

  it("works at a pen change, and shows how far over the pen will plot", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    const panel = await mount("rp-plotter");
    const root = shadow(panel);
    expect(labelled(root, "Move pen right").getAttribute("aria-disabled")).toBe("false");
    labelled(root, "Step 0.5 mm").click();
    await settle();
    labelled(root, "Move pen down (on screen)").click();
    await settle();
    await settle();
    expect(fake.called("plot_align_jog")).toEqual([[0, 0.5]]);
    expect(root.querySelector(".offset")?.textContent?.replace(/\s+/g, " ").trim()).toBe("This pen plots X 0.00, Y +0.50 mm over");
    const press = (text: string) => (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === text) as HTMLButtonElement).click();
    press("Pen down");
    await settle();
    expect(fake.called("plot_align_pen")).toEqual([[true]]);
    const before = fake.called("plotter_motors_off").length;
    press("Release motors"); // not in the middle of a plot
    await settle();
    expect(fake.called("plotter_motors_off")).toHaveLength(before);
  });

  it("Release motors lets go without starting Set Home", async () => {
    const { app, fake } = await startApp();
    const root = shadow(await mount("rp-plotter"));
    await app.setHome();
    await app.setHome();
    await settle();
    fake.calls.length = 0;
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Release motors") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("plotter_motors_off")).toHaveLength(1);
    expect(app.state.machine.state).toBe("not_homed");
    expect(app.state.homing).toBe(false);
    expect(app.state.notice?.message).toMatch(/^Motors released/);
  });

  it("sets the pen height live", async () => {
    const { fake } = await startApp();
    const root = shadow(await mount("rp-plotter"));
    const slider = labelled(root, "Pen-down height") as HTMLInputElement;
    slider.value = "45";
    slider.dispatchEvent(new Event("input"));
    await settle();
    expect(fake.called("pen_set").at(-1)).toEqual([45, "fineliner"]);
    expect(root.textContent).toContain("45");
  });
});

describe("dock", () => {
  it("collapses a panel", async () => {
    await startApp();
    const root = shadow(await mount("rp-dock"));
    const header = root.querySelector('section.jobs button[aria-expanded="true"]') as HTMLButtonElement;
    header.click();
    await settle();
    expect(root.querySelector("rp-jobs")).toBeNull();
    expect(root.querySelector("rp-pens")).not.toBeNull();
  });
});

describe("jog pad: press and hold", () => {
  function press(el: HTMLElement, type: string) {
    el.dispatchEvent(new PointerEvent(type, { bubbles: true, button: 0, pointerId: 1 }));
  }

  it("a press and release moves one step; a keyboard click moves one step", async () => {
    const { app, fake } = await startApp();
    await app.setHome();
    await app.setHome();
    const root = shadow(await mount("rp-plotter"));
    await settle();
    const right = labelled(root, "Move pen right");
    press(right, "pointerdown");
    press(right, "pointerup");
    await settle();
    right.click(); // Enter or Space on the focused button
    await settle();
    expect(fake.called("plotter_jog")).toEqual([[1, 0], [1, 0]]);
  });

  it("lets go when the window loses focus", async () => {
    const { app } = await startApp();
    await app.setHome();
    await app.setHome();
    const root = shadow(await mount("rp-plotter"));
    await settle();
    press(labelled(root, "Move pen right"), "pointerdown");
    const release = vi.spyOn(app, "jogRelease"); // after the press, which lets go of any earlier hold itself
    window.dispatchEvent(new Event("blur"));
    expect(release).toHaveBeenCalled();
    app.jogRelease();
  });

  it("lets go when the pointer slides off the arrow", async () => {
    const { app } = await startApp();
    await app.setHome();
    await app.setHome();
    const root = shadow(await mount("rp-plotter"));
    await settle();
    const right = labelled(root, "Move pen right");
    right.getBoundingClientRect = () => ({ left: 0, top: 0, right: 32, bottom: 32, width: 32, height: 32, x: 0, y: 0, toJSON: () => ({}) });
    press(right, "pointerdown");
    const release = vi.spyOn(app, "jogRelease");
    right.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: 16, clientY: 16, pointerId: 1 }));
    expect(release).not.toHaveBeenCalled();
    right.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: 80, clientY: 16, pointerId: 1 }));
    expect(release).toHaveBeenCalled();
    app.jogRelease();
  });
});
