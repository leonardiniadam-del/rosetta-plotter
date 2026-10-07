import { describe, expect, it } from "vitest";
import "./menubar";
import { handleShortcut, installShortcuts } from "../shortcuts";
import { mount, settle, shadow, startApp } from "../test/setup";

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
