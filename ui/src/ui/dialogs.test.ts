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
