import { describe, expect, it } from "vitest";
import "./plotbar";
import "./controlbar";
import "./statusbar";
import { mount, readyToPlot, settle, shadow, startApp } from "../test/setup";
import type { RpField } from "./field";

type Lit = HTMLElement & { updateComplete: Promise<unknown> };

function button(root: ShadowRoot, label: string): HTMLButtonElement {
  const found = Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === label);
  if (!found) throw new Error(`no button ${label}`);
  return found as HTMLButtonElement;
}

describe("plot bar", () => {
  it("shows each pen's time and the total, and Start is ready", async () => {
    const { app } = await readyToPlot();
    const bar = await mount<Lit>("rp-plotbar");
    const root = shadow(bar);
    expect(root.querySelectorAll(".chip")).toHaveLength(2);
    expect(root.querySelector(".total")?.textContent).toMatch(/^Total \d+:\d\d$/);
    expect(button(root, "Start").getAttribute("aria-disabled")).toBe("false");
    expect(button(root, "Pause").getAttribute("aria-disabled")).toBe("true");
    button(root, "Start").click();
    await settle();
    expect(app.state.plot.state).toBe("load_pen");
  });

  it("says why Start is greyed out when clicked", async () => {
    const { app } = await readyToPlot();
    app.store.update({ summary: null, preparing: true });
    const root = shadow(await mount<Lit>("rp-plotbar"));
    expect(root.querySelector(".total")?.textContent).toBe("…");
    button(root, "Start").click();
    expect(app.state.notice?.message).toBe("The plot is being prepared.");
  });

  it("while paused Resume, Return Home and Cancel plot work", async () => {
    const { app } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    await app.plotAction("pause");
    await settle();
    const bar = await mount<Lit>("rp-plotbar");
    const labels = Array.from(shadow(bar).querySelectorAll("button")).map((b) => b.textContent?.trim());
    expect(labels).toEqual(["Set Home", "Start", "Pause", "Resume", "Return Home", "Cancel plot"]);
    const root = shadow(bar);
    expect(button(root, "Resume").getAttribute("aria-disabled")).toBe("false");
    expect(button(root, "Return Home").getAttribute("aria-disabled")).toBe("false");
    expect(button(root, "Start").getAttribute("aria-disabled")).toBe("true");
  });

  it("Return Home sends the pen Home when nothing is plotting", async () => {
    const { fake } = await readyToPlot();
    const root = shadow(await mount<Lit>("rp-plotbar"));
    expect(button(root, "Resume").getAttribute("aria-disabled")).toBe("true");
    button(root, "Return Home").click();
    await settle();
    expect(fake.called("plotter_goto")).toEqual([[0, 0]]);
  });

  it("Cancel plot asks first, then cancels", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    await app.plotAction("pause");
    await settle();
    const root = shadow(await mount<Lit>("rp-plotbar"));
    button(root, "Cancel plot").click();
    expect(app.state.dialog).toMatchObject({
      kind: "confirm",
      title: "Cancel the plot?",
      message: "This plot can't be resumed.",
      confirm: "Cancel plot",
      cancel: "Keep plot",
    });
    expect(fake.called("plot_cancel")).toHaveLength(0);
    const dialog = app.state.dialog as { run: () => void };
    dialog.run();
    await settle();
    expect(app.state.dialog).toBeNull();
    expect(fake.called("plot_cancel")).toHaveLength(1);
  });

  it("the warnings chip is readable by a screen reader", async () => {
    const { app } = await readyToPlot();
    app.store.update((s) => ({ summary: s.summary && { ...s.summary, warnings: ["Part of the drawing is off the paper."] } }));
    const root = shadow(await mount<Lit>("rp-plotbar"));
    const warn = root.querySelector(".warn");
    expect(warn?.getAttribute("role")).toBe("img");
    expect(warn?.getAttribute("aria-label")).toBe("Part of the drawing is off the paper.");
  });

  it("shows time left while plotting", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    fake.progress(0.5);
    const bar = await mount<Lit>("rp-plotbar");
    expect(shadow(bar).querySelector(".total")?.textContent).toMatch(/left$/);
  });

  it("greys the buttons and says what is happening while pausing", async () => {
    const { app } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    app.store.update((s) => ({ plot: { ...s.plot, state: "pausing" } }));
    const root = shadow(await mount<Lit>("rp-plotbar"));
    expect(root.querySelector(".waiting")?.textContent).toBe("Pausing…");
    for (const label of ["Start", "Pause", "Stop"]) expect(button(root, label).getAttribute("aria-disabled")).toBe("true");
  });
});

describe("control bar while plotting", () => {
  it("locks the paper fields and draws the progress line", async () => {
    const { app, fake } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    fake.progress(0.5);
    await settle();
    const bar = await mount<Lit>("rp-controlbar");
    await bar.updateComplete;
    const root = shadow(bar);
    app.store.update({ selection: [] });
    await bar.updateComplete;
    const width = Array.from(root.querySelectorAll("rp-field")).find((f) => (f as RpField).label === "W") as RpField;
    expect(width.hasAttribute("disabled")).toBe(true);
    expect(root.querySelector("rp-plotbar")).not.toBeNull();
    expect(root.querySelector(".progress")).not.toBeNull();
  });

  it("keeps the plot buttons outside the scrolling left controls", async () => {
    // jsdom can't measure layout, so this checks the structure the CSS relies on: the left controls scroll
    // in their own container and the plot bar is its sibling, so Start/Pause/Stop can't be clipped.
    await readyToPlot();
    const bar = await mount<Lit>("rp-controlbar");
    const root = shadow(bar);
    const children = Array.from(root.children).filter((c) => c.tagName !== "STYLE");
    expect(children.map((c) => c.className || c.tagName.toLowerCase())).toEqual(["left", "rp-plotbar"]);
    const css = (bar.constructor as unknown as { styles: Array<{ cssText: string }> }).styles.map((x) => x.cssText).join("");
    expect(css).toMatch(/\.left\s*\{[^}]*overflow-x:\s*auto/);
    expect(css).toMatch(/\.left\s*\{[^}]*min-width:\s*0/);
  });

  it("shows no progress line when nothing is plotting", async () => {
    await readyToPlot();
    const root = shadow(await mount<Lit>("rp-controlbar"));
    expect(root.querySelector(".progress")).toBeNull();
  });
});

describe("status bar while plotting", () => {
  it("asks to keep the laptop open", async () => {
    const { app } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    const bar = await mount<Lit>("rp-statusbar");
    expect(shadow(bar).textContent).not.toContain("Keep the laptop open while plotting.");
    await app.startPlot();
    await settle();
    await bar.updateComplete;
    expect(shadow(bar).textContent).toContain("Keep the laptop open while plotting.");
  });
});

describe("Set Home on the plot bar", () => {
  it("sits just left of Start", async () => {
    await readyToPlot();
    const labels = Array.from(shadow(await mount<Lit>("rp-plotbar")).querySelectorAll("button")).map((b) => b.textContent?.trim());
    expect(labels).toEqual(["Set Home", "Start", "Pause", "Resume", "Return Home", "Stop"]);
  });

  it("runs the two-click Set Home", async () => {
    const { app, fake } = await startApp();
    const bar = await mount<Lit>("rp-plotbar");
    const root = shadow(bar);
    button(root, "Set Home").click();
    await settle();
    const confirm = button(root, "Confirm Home");
    expect(confirm.classList.contains("active")).toBe(true);
    expect(confirm.title).toBe("Slide the pen to the HOME corner, then click again (Esc cancels)");
    expect(fake.called("plotter_motors_off")).toHaveLength(1);
    confirm.click();
    await settle();
    expect(button(root, "Set Home").classList.contains("active")).toBe(false);
    expect(app.state.machine.state).toBe("ready");
  });

  it("is greyed with the Set Home reason", async () => {
    const { app } = await startApp();
    app.store.update((s) => ({ machine: { ...s.machine, state: "no_plotter" } }));
    const root = shadow(await mount<Lit>("rp-plotbar"));
    const setHome = button(root, "Set Home");
    expect(setHome.getAttribute("aria-disabled")).toBe("true");
    setHome.click();
    expect(app.state.notice?.message).toBe("No plotter connected. Plug in the USB cable and the power adapter.");
  });
});
