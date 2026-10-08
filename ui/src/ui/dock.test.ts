import { describe, expect, it } from "vitest";
import "./dock";
import { mount, settle, shadow, startApp } from "../test/setup";

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
    labelled(root, "Step 1 mm").click();
    await settle();
    labelled(root, "Move pen toward you").click();
    await settle();
    expect(fake.called("plotter_jog")).toEqual([[1, 0], [0, 10]]);
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
