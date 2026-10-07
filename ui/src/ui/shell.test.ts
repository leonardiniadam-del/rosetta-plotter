import { describe, expect, it } from "vitest";
import "./app-shell";
import { mount, settle, shadow, startApp } from "../test/setup";

function button(root: ShadowRoot, label: string): HTMLButtonElement {
  const found = root.querySelector(`button[aria-label^="${label}"]`);
  if (!found) throw new Error(`no button labelled ${label}`);
  return found as HTMLButtonElement;
}

describe("window shell", () => {
  it("has every region of the manager window", async () => {
    await startApp();
    const root = shadow(await mount("rp-app"));
    for (const tag of ["rp-menubar", "rp-controlbar", "rp-tools", "rp-plate", "rp-dock", "rp-statusbar", "rp-strip", "rp-dialogs"]) {
      expect(root.querySelector(tag), tag).not.toBeNull();
    }
  });
});

describe("status bar", () => {
  it("shows the plotter, Home and units", async () => {
    const { app, fake } = await startApp();
    const bar = await mount("rp-statusbar");
    const root = shadow(bar);
    expect(root.textContent).toContain("AxiDraw SE/A1");
    expect(root.textContent).toContain("Power OK");
    expect(root.textContent).toContain("Home not set");
    app.cursor.update({ point: [25.4, 50.8] });
    await settle();
    expect(root.textContent).toContain("Cursor 1.00, 2.00");
    const units = root.querySelector('select[aria-label="Units"]') as HTMLSelectElement;
    units.value = "mm";
    units.dispatchEvent(new Event("change"));
    await settle();
    expect(fake.called("set_units")).toEqual([["mm"]]);
    expect(root.textContent).toContain("Cursor 25.4, 50.8");
  });
});

describe("tools", () => {
  it("switches tools", async () => {
    const { app } = await startApp();
    const root = shadow(await mount("rp-tools"));
    button(root, "Hand").click();
    expect(app.state.tool).toBe("hand");
  });

  it("sets Home in two clicks, the button staying pressed in between", async () => {
    const { app } = await startApp();
    const tools = await mount("rp-tools");
    const root = shadow(tools);
    button(root, "Set Home").click();
    await settle();
    expect(app.state.homing).toBe(true);
    const pressed = button(root, "Slide the pen");
    expect(pressed.getAttribute("aria-pressed")).toBe("true");
    pressed.click();
    await settle();
    expect(app.state.machine.state).toBe("ready");
  });

  it("explains a greyed-out tool instead of acting", async () => {
    const { app } = await startApp();
    const root = shadow(await mount("rp-tools"));
    const pen = button(root, "Move pen to point");
    expect(pen.getAttribute("aria-disabled")).toBe("true");
    expect(pen.title).toContain("Home not set");
    pen.click();
    expect(app.state.tool).toBe("select");
    expect(app.state.notice?.message).toMatch(/^Home not set/);
  });
});
