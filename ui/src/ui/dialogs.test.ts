import { describe, expect, it } from "vitest";
import "./dialogs";
import { handleShortcut } from "../shortcuts";
import { mount, readyToPlot, settle, shadow, startApp } from "../test/setup";

type Lit = HTMLElement & { updateComplete: Promise<unknown> };

describe("plotter model dialog", () => {
  it("has no model chosen when the plotter's model is unknown, and Save explains", async () => {
    const { app, fake } = await startApp();
    fake.model = null;
    await app.scan();
    const dialogs = await mount<Lit>("rp-dialogs");
    app.openModelDialog();
    await dialogs.updateComplete;
    const root = shadow(dialogs);
    expect(root.querySelector('input[name="model"]:checked')).toBeNull();
    const save = root.querySelector("button.primary") as HTMLButtonElement;
    expect(save.getAttribute("aria-disabled")).toBe("true");
    save.click();
    await dialogs.updateComplete;
    expect(fake.called("plotter_identify")).toEqual([]);
    expect(root.querySelector(".hint")?.textContent).toBe("Choose the model on the plotter's label first.");
    const a2 = root.querySelector('input[name="model"][value="6"]') as HTMLInputElement;
    a2.checked = true;
    a2.dispatchEvent(new Event("change"));
    await dialogs.updateComplete;
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("plotter_identify")).toEqual([[6, 1, ""]]); // no stored label while the model is unknown
  });

  it("focuses the checked model first", async () => {
    const { app } = await startApp();
    const dialogs = await mount<Lit>("rp-dialogs");
    app.openModelDialog();
    await dialogs.updateComplete;
    await dialogs.updateComplete;
    const active = shadow(dialogs).activeElement as HTMLInputElement | null;
    expect(active?.matches('input[name="model"]:checked')).toBe(true);
  });

  it("takes focus, and Enter confirms", async () => {
    const { app } = await startApp();
    const dialogs = await mount<Lit>("rp-dialogs");
    app.showDialog("about");
    await dialogs.updateComplete;
    await dialogs.updateComplete;
    expect(shadow(dialogs).activeElement?.tagName).toBe("BUTTON");
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await dialogs.updateComplete;
    expect(app.state.dialog).toBeNull();
  });
});

describe("shortcuts while a dialog is open", () => {
  it("only Esc works", async () => {
    const { app, fake } = await startApp();
    await app.importFiles();
    await app.placeJob("job-1");
    app.showDialog("about");
    const used = handleShortcut(app, new KeyboardEvent("keydown", { key: "Delete" }));
    handleShortcut(app, new KeyboardEvent("keydown", { key: "i", ctrlKey: true }));
    await settle();
    expect(used).toBe(false);
    expect(fake.called("piece_delete")).toEqual([]);
    expect(fake.called("artwork_choose")).toHaveLength(1); // only the import above
    expect(app.state.dialog?.kind).toBe("about");
  });

  it("Delete does nothing while the plot asks for a pen", async () => {
    const { app, fake } = await readyToPlot();
    await app.startPlot();
    expect(app.state.plot.state).toBe("load_pen");
    const used = handleShortcut(app, new KeyboardEvent("keydown", { key: "Delete" }));
    await settle();
    expect(used).toBe(false);
    expect(fake.called("piece_delete")).toEqual([]);
  });
});

describe("plot dialogs", () => {
  it("asks for the next pen, and Continue plots it", async () => {
    const { app } = await readyToPlot();
    const dialogs = await mount<Lit>("rp-dialogs");
    await app.startPlot();
    await dialogs.updateComplete;
    const root = shadow(dialogs);
    expect(root.querySelector("h2")?.textContent).toBe("Change the pen");
    expect(root.querySelector(".message")?.textContent).toBe("Put the black pen in the holder (1 of 2), then click Continue.");
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await settle();
    expect(app.state.plot.state).toBe("plotting");
  });

  it("focuses Continue, so Enter continues rather than cancels the plot", async () => {
    const { app } = await readyToPlot();
    const dialogs = await mount<Lit>("rp-dialogs");
    await app.startPlot();
    await dialogs.updateComplete;
    await dialogs.updateComplete;
    const active = shadow(dialogs).activeElement as HTMLButtonElement | null;
    expect(active?.textContent?.trim()).toBe("Continue");
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await settle();
    expect(app.state.plot.state).toBe("plotting");
  });

  it("Esc doesn't cancel the plot from the pen-change dialog", async () => {
    const { app } = await readyToPlot();
    await mount<Lit>("rp-dialogs");
    await app.startPlot();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    await settle();
    expect(app.state.plot.state).toBe("load_pen");
  });

  it("draws a confirmation with its two buttons", async () => {
    const { app } = await startApp();
    const dialogs = await mount<Lit>("rp-dialogs");
    let ran = false;
    app.store.update({ dialog: { kind: "confirm", title: "Stop the plot?", message: "The pen lifts.", confirm: "Stop", cancel: "Keep plotting", run: () => (ran = true) } });
    await dialogs.updateComplete;
    const labels = Array.from(shadow(dialogs).querySelectorAll("button")).map((b) => b.textContent?.trim());
    expect(labels).toEqual(["Keep plotting", "Stop"]);
    (shadow(dialogs).querySelector("button.primary") as HTMLButtonElement).click();
    expect(ran).toBe(true);
  });
});

describe("Settings", () => {
  async function openSettings() {
    const started = await startApp();
    const dialogs = await mount<Lit>("rp-dialogs");
    started.app.openSettings();
    await dialogs.updateComplete;
    return { ...started, dialogs, root: shadow(dialogs) };
  }

  function tab(root: ShadowRoot, name: string) {
    (Array.from(root.querySelectorAll('[role="tab"]')).find((b) => b.textContent?.trim() === name) as HTMLButtonElement).click();
  }

  it("General applies at once: skip white shapes", async () => {
    const { fake, root } = await openSettings();
    const skip = root.querySelector("#skip-white") as HTMLInputElement;
    skip.checked = false;
    skip.dispatchEvent(new Event("change"));
    await settle();
    expect(fake.called("set_skip_white")).toEqual([[false]]);
  });

  it("General applies at once: units and the grid", async () => {
    const { app, fake, root } = await openSettings();
    const units = root.querySelector("#units") as HTMLSelectElement;
    units.value = "mm";
    units.dispatchEvent(new Event("change"));
    await settle();
    expect(fake.called("set_units")).toEqual([["mm"]]);
    expect(app.state.units).toBe("mm");
    const grid = root.querySelector("#grid") as HTMLInputElement;
    grid.checked = false;
    grid.dispatchEvent(new Event("change"));
    expect(app.state.view.grid).toBe(false);
  });

  it("Advanced sends only what changed, after checking it", async () => {
    const { app, fake, dialogs, root } = await openSettings();
    tab(root, "Advanced");
    await dialogs.updateComplete;
    const accel = root.querySelector("#adv-accel") as HTMLInputElement;
    accel.value = "500";
    accel.dispatchEvent(new Event("change"));
    await dialogs.updateComplete;
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await dialogs.updateComplete;
    expect(root.querySelector(".hint")?.textContent).toBe("Acceleration must be from 1 to 100.");
    expect(fake.called("set_advanced")).toEqual([]);
    accel.value = "60";
    accel.dispatchEvent(new Event("change"));
    await dialogs.updateComplete;
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("set_advanced")).toEqual([[{ accel: 60 }]]);
    expect(app.state.advanced.accel).toBe(60);
    expect(app.state.dialog).toBeNull();
  });

  it("Enter in a number box saves what was just typed", async () => {
    const { app, fake, dialogs, root } = await openSettings();
    tab(root, "Advanced");
    await dialogs.updateComplete;
    const accel = root.querySelector("#adv-accel") as HTMLInputElement;
    accel.focus();
    accel.value = "60";
    accel.dispatchEvent(new Event("input")); // typing; the browser's change event comes after Enter
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await settle();
    expect(fake.called("set_advanced")).toEqual([[{ accel: 60 }]]);
    expect(app.state.dialog).toBeNull();
  });

  it("shows Python's message when it refuses the options, and keeps the dialog open", async () => {
    const { app, fake, dialogs, root } = await openSettings();
    tab(root, "Advanced");
    await dialogs.updateComplete;
    const penUp = root.querySelector("#adv-pen_up") as HTMLInputElement;
    expect(penUp.disabled).toBe(true); // Automatic
    const automatic = root.querySelector("#adv-pen_up ~ label input") as HTMLInputElement;
    automatic.checked = false;
    automatic.dispatchEvent(new Event("change"));
    await dialogs.updateComplete;
    penUp.value = "35";
    penUp.dispatchEvent(new Event("change"));
    await dialogs.updateComplete;
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await settle();
    await dialogs.updateComplete;
    expect(fake.called("set_advanced")).toEqual([[{ pen_up: 35 }]]);
    expect(root.querySelector(".hint")?.textContent).toBe("Pen-up height must be at least 10 above the pen-down height (30).");
    expect(app.state.dialog?.kind).toBe("settings");
    expect(app.state.advanced.pen_up).toBeNull();
  });

  it("Restore defaults puts every option back", async () => {
    const { app, fake, dialogs, root } = await openSettings();
    await app.setAdvanced({ accel: 60, hiding: true });
    tab(root, "Advanced");
    await dialogs.updateComplete;
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Restore defaults") as HTMLButtonElement).click();
    await dialogs.updateComplete;
    (root.querySelector("button.primary") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("set_advanced").at(-1)).toEqual([{ accel: 75, hiding: false }]);
  });

  it("Cancel on Advanced sends nothing", async () => {
    const { app, fake, dialogs, root } = await openSettings();
    tab(root, "Advanced");
    await dialogs.updateComplete;
    const accel = root.querySelector("#adv-accel") as HTMLInputElement;
    accel.value = "60";
    accel.dispatchEvent(new Event("change"));
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Cancel") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("set_advanced")).toEqual([]);
    expect(app.state.dialog).toBeNull();
  });
  it("Enter and Esc in the margin box act on the box first", async () => {
    const { app, fake, dialogs, root } = await openSettings();
    const field = root.querySelector("rp-field") as HTMLElement;
    const box = shadow(field).querySelector("input") as HTMLInputElement;
    box.focus();
    box.value = "0.5";
    box.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, composed: true }));
    await settle();
    await dialogs.updateComplete;
    expect(fake.called("set_margin").length).toBe(1);
    expect(app.state.dialog?.kind).toBe("settings");
    // Esc reverts the box and leaves the dialog open
    box.focus();
    box.value = "0.9";
    box.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }));
    await settle();
    expect(fake.called("set_margin").length).toBe(1);
    expect(app.state.dialog?.kind).toBe("settings");
    // a second Esc, with focus no longer in the box, closes
    (box as HTMLElement).blur();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    await settle();
    expect(app.state.dialog).toBeNull();
  });

  it("keeps the Advanced draft through a pen change", async () => {
    const { app, dialogs, root } = await openSettings();
    tab(root, "Advanced");
    await dialogs.updateComplete;
    const accel = root.querySelector("#adv-accel") as HTMLInputElement;
    accel.value = "60";
    accel.dispatchEvent(new Event("input"));
    await dialogs.updateComplete;
    app.store.update((s) => ({ plot: { ...s.plot, state: "load_pen" } }));
    await dialogs.updateComplete;
    app.store.update((s) => ({ plot: { ...s.plot, state: "plotting" } }));
    await dialogs.updateComplete;
    await dialogs.updateComplete;
    expect(root.querySelector('[role="tab"][aria-selected="true"]')?.textContent?.trim()).toBe("Advanced");
    expect((root.querySelector("#adv-accel") as HTMLInputElement).value).toBe("60");
  });

  it("Save ignores a second click while the first is on its way", async () => {
    const { fake, dialogs, root } = await openSettings();
    tab(root, "Advanced");
    await dialogs.updateComplete;
    const accel = root.querySelector("#adv-accel") as HTMLInputElement;
    accel.value = "60";
    accel.dispatchEvent(new Event("input"));
    await dialogs.updateComplete;
    const release = fake.hold("set_advanced");
    const save = root.querySelector("button.primary") as HTMLButtonElement;
    save.click();
    await dialogs.updateComplete;
    expect(save.getAttribute("aria-disabled")).toBe("true");
    save.click();
    release();
    await settle();
    expect(fake.called("set_advanced").length).toBe(1);
  });
});
