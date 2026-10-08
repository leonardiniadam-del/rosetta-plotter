import { describe, expect, it } from "vitest";
import "./plotbar";
import "./controlbar";
import "./statusbar";
import { mount, readyToPlot, settle, shadow } from "../test/setup";
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

  it("while paused offers Resume, Return Home and Cancel plot", async () => {
    const { app } = await readyToPlot();
    await app.setPenVisible("#ff0000", false);
    await settle();
    await settle();
    await app.startPlot();
    await app.plotAction("pause");
    await settle();
    const bar = await mount<Lit>("rp-plotbar");
    const labels = Array.from(shadow(bar).querySelectorAll("button")).map((b) => b.textContent?.trim());
    expect(labels).toEqual(["Resume", "Return Home", "Cancel plot"]);
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
