import { describe, expect, it } from "vitest";
import "./dialogs";
import { handleShortcut } from "../shortcuts";
import { mount, settle, shadow, startApp } from "../test/setup";

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
});
