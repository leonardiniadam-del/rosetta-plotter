import { describe, expect, it } from "vitest";
import "./menubar";
import { handleShortcut, installShortcuts } from "../shortcuts";
import { mount, readyToPlot, settle, shadow, startApp } from "../test/setup";

function key(init: KeyboardEventInit): KeyboardEvent {
  return new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init });
}

async function openMenu(root: ShadowRoot, name: string) {
  (Array.from(root.querySelectorAll("button.title")).find((b) => b.textContent?.trim() === name) as HTMLButtonElement).click();
  await settle();
}

function item(root: ShadowRoot, label: string): HTMLButtonElement {
  const found = Array.from(root.querySelectorAll('.menu [role^="menuitem"]')).find((b) => b.querySelector(".label")?.textContent === label);
  if (!found) throw new Error(`no menu item ${label}`);
  return found as HTMLButtonElement;
}

describe("menu bar", () => {
  it("imports from File", async () => {
    const { fake } = await startApp();
    const root = shadow(await mount("rp-menubar"));
    await openMenu(root, "File");
    item(root, "Import…").click();
    await settle();
    expect(fake.called("artwork_choose")).toHaveLength(1);
    expect(root.querySelector(".menu")).toBeNull();
  });

  it("explains a greyed-out item", async () => {
    const { app, fake } = await startApp();
    const root = shadow(await mount("rp-menubar"));
    await openMenu(root, "Object");
    const duplicate = item(root, "Duplicate");
    expect(duplicate.getAttribute("aria-disabled")).toBe("true");
    duplicate.click();
    expect(fake.called("piece_duplicate")).toEqual([]);
    expect(app.state.notice?.message).toBe("Select a drawing first.");
  });

  it("switches units and view options from View", async () => {
    const { app } = await startApp();
    const root = shadow(await mount("rp-menubar"));
    await openMenu(root, "View");
    item(root, "Millimeters").click();
    await settle();
    expect(app.state.units).toBe("mm");
    await openMenu(root, "View");
    expect(item(root, "Millimeters").getAttribute("aria-checked")).toBe("true");
    item(root, "Show grid").click();
    expect(app.state.view.grid).toBe(false);
  });
});

describe("shortcuts", () => {
  async function withSelection() {
    const started = await startApp();
    await started.app.importFiles();
    await started.app.placeJob("job-1");
    return started;
  }

  it("duplicates, turns and stops the browser's own meaning", async () => {
    const { app, fake } = await withSelection();
    expect(handleShortcut(app, key({ key: "d", ctrlKey: true }))).toBe(true);
    await settle();
    expect(fake.called("piece_duplicate")).toEqual([["piece-1"]]);
    const reload = key({ key: "r", ctrlKey: true });
    const stop = installShortcuts(app);
    window.dispatchEvent(reload);
    stop();
    expect(reload.defaultPrevented).toBe(true);
    await settle();
    expect(app.state.pieces.find((p) => p.id === app.state.selection[0])?.placement.rotation).toBe(90);
  });

  it("nudges the selection with the arrows", async () => {
    const { app } = await withSelection();
    handleShortcut(app, key({ key: "ArrowRight" }));
    await settle();
    handleShortcut(app, key({ key: "ArrowDown", shiftKey: true }));
    await settle();
    expect(app.state.pieces[0].placement.x).toBeCloseTo(7.35);
    expect(app.state.pieces[0].placement.y).toBeCloseTo(16.35);
  });

  it("picks tools with letters, but not while typing", async () => {
    const { app } = await startApp();
    handleShortcut(app, key({ key: "h" }));
    expect(app.state.tool).toBe("hand");
    const input = document.createElement("input");
    document.body.append(input);
    const stop = installShortcuts(app);
    input.dispatchEvent(key({ key: "v" }));
    stop();
    expect(app.state.tool).toBe("hand");
  });

  it("cancels Set Home with Esc", async () => {
    const { app } = await startApp();
    await app.setHome();
    handleShortcut(app, key({ key: "Escape" }));
    expect(app.state.homing).toBe(false);
  });
});

describe("menus and Esc", () => {
  it("Esc closes an open menu without deselecting", async () => {
    const { app } = await startApp();
    await app.importFiles();
    await app.placeJob("job-1");
    const bar = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-menubar");
    (Array.from(shadow(bar).querySelectorAll("button.title")).find((b) => b.textContent?.trim() === "View") as HTMLButtonElement).click();
    await bar.updateComplete;
    const esc = new KeyboardEvent("keydown", { key: "Escape", bubbles: true });
    let reachedPage = false;
    window.addEventListener("keydown", () => (reachedPage = true), { once: true });
    document.body.dispatchEvent(esc);
    await bar.updateComplete;
    expect(shadow(bar).querySelector('[role="menu"]')).toBeNull();
    expect(reachedPage).toBe(false);
    expect(app.state.selection).toEqual(["piece-1"]);
  });

  it("Units are radio items", async () => {
    await startApp();
    const bar = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-menubar");
    (Array.from(shadow(bar).querySelectorAll("button.title")).find((b) => b.textContent?.trim() === "View") as HTMLButtonElement).click();
    await bar.updateComplete;
    const inches = Array.from(shadow(bar).querySelectorAll('[role="menu"] button')).find((b) => b.textContent?.includes("Inches"));
    expect(inches?.getAttribute("role")).toBe("menuitemradio");
  });
});

describe("plot commands", () => {
  it("the Plotter menu has the plot commands, greyed with reasons", async () => {
    await startApp();
    const bar = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-menubar");
    const root = shadow(bar);
    await openMenu(root, "Plotter");
    const items = Array.from(root.querySelectorAll('[role="menu"] button')).map((b) => b.querySelector(".label")?.textContent);
    expect(items).toEqual(expect.arrayContaining(["Trace outline", "Preview path", "Start", "Pause", "Stop"]));
    expect(item(root, "Start").getAttribute("aria-disabled")).toBe("true");
    expect(item(root, "Start").title).not.toBe("");
  });

  it("Settings… is in the File menu", async () => {
    const { app } = await startApp();
    const root = shadow(await mount("rp-menubar"));
    await openMenu(root, "File");
    item(root, "Settings…").click();
    await settle();
    expect(app.state.dialog?.kind).toBe("settings");
  });

  it("the Plotter menu starts a preview when a plot is possible", async () => {
    const { app } = await readyToPlot();
    const root = shadow(await mount("rp-menubar"));
    await openMenu(root, "Plotter");
    item(root, "Preview path").click();
    await settle();
    expect(app.state.preview).not.toBeNull();
    app.endPreview();
  });

  it("Ctrl+Enter starts, Ctrl+Shift+P pauses, Ctrl+, opens Settings", async () => {
    const { app } = await readyToPlot();
    expect(handleShortcut(app, new KeyboardEvent("keydown", { key: "Enter", ctrlKey: true }))).toBe(true);
    await settle();
    expect(app.state.plot.state).toBe("load_pen");
    await app.plotAction("continue");
    handleShortcut(app, new KeyboardEvent("keydown", { key: "P", ctrlKey: true, shiftKey: true }));
    await settle();
    expect(["pausing", "paused"]).toContain(app.state.plot.state);
    const other = await startApp();
    handleShortcut(other.app, new KeyboardEvent("keydown", { key: ",", ctrlKey: true }));
    expect(other.app.state.dialog?.kind).toBe("settings");
  });

  it("Ctrl+P is swallowed so the WebView's print dialog doesn't open", async () => {
    const { app } = await startApp();
    expect(handleShortcut(app, new KeyboardEvent("keydown", { key: "p", ctrlKey: true }))).toBe(true);
  });
});
