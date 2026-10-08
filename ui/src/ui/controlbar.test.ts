import { describe, expect, it } from "vitest";
import "./controlbar";
import { mount, settle, shadow, startApp } from "../test/setup";
import type { RpField } from "./field";

type RpControlbarLike = HTMLElement & { updateComplete: Promise<unknown> };

function field(root: ShadowRoot, label: string): RpField {
  const found = Array.from(root.querySelectorAll("rp-field")).find((f) => (f as RpField).label === label);
  if (!found) throw new Error(`no field ${label}`);
  return found as RpField;
}

function commit(target: RpField, value: number) {
  target.dispatchEvent(new CustomEvent("commit", { detail: value }));
}

describe("control bar, nothing selected", () => {
  it("sets the paper", async () => {
    const { app, fake } = await startApp();
    const bar = await mount("rp-controlbar");
    const root = shadow(bar);
    const size = root.querySelector('select[aria-label="Paper size"]') as HTMLSelectElement;
    size.value = "a4";
    size.dispatchEvent(new Event("change"));
    await settle();
    expect(fake.called("material_set").at(-1)).toEqual(["a4", "landscape", null, null, 0, 0]);
    expect(field(root, "W").value).toBe(297);
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Portrait") as HTMLButtonElement).click();
    await settle();
    expect(app.state.paper.orientation).toBe("portrait");
    commit(field(root, "Margin"), 12.7);
    await settle();
    expect(app.state.margin).toBe(12.7);
  });

  it("the paper list shows the paper actually in use", async () => {
    const { app } = await startApp();
    const root = shadow(await mount("rp-controlbar"));
    const size = root.querySelector('select[aria-label="Paper size"]') as HTMLSelectElement;
    size.value = "a4"; // picked, but the change never reached Python
    app.store.update((s) => ({ paper: { ...s.paper } }));
    await (root.host as RpControlbarLike).updateComplete;
    expect(size.value).toBe("letter");
  });

  it("types a custom size only for Custom paper", async () => {
    const { fake } = await startApp();
    const root = shadow(await mount("rp-controlbar"));
    expect(field(root, "W").readonly).toBe(true);
    commit(field(root, "W"), 500);
    await settle();
    expect(fake.called("material_set").at(-1)).toEqual(["custom", "landscape", 500, 215.9, 0, 0]);
  });
});

describe("control bar, a drawing selected", () => {
  async function selected() {
    const started = await startApp();
    await started.app.importFiles();
    await started.app.placeJob("job-1"); // 120 x 80 at (6.35, 6.35), selected
    const root = shadow(await mount("rp-controlbar"));
    return { ...started, root };
  }

  it("shows the drawing's numbers in the chosen units", async () => {
    const { root } = await selected();
    expect(root.textContent).toContain("site-plan");
    expect(field(root, "X").value).toBeCloseTo(6.35);
    expect(field(root, "W").value).toBe(120);
    expect(field(root, "W").units).toBe("in");
    expect(field(root, "Scale").value).toBe(1);
  });

  it("resizes, scales, unlinks and turns", async () => {
    const { app, fake, root } = await selected();
    commit(field(root, "W"), 240);
    await settle();
    expect(fake.called("piece_place").at(-1)?.slice(3)).toEqual([2, 0, 2]);
    (root.querySelector('button[aria-label^="Proportions linked"]') as HTMLButtonElement).click();
    await settle();
    commit(field(root, "H%"), 0.5);
    await settle();
    expect(app.state.pieces[0].placement).toMatchObject({ scale: 2, scale_y: 0.5 });
    commit(field(root, "Angle"), 90);
    await settle();
    expect(app.state.pieces[0].placement.rotation).toBe(90);
  });

  it("with the link on, editing W% of a stretched drawing scales both", async () => {
    const { app, root } = await selected();
    await app.setScale(1, 2); // stretched: W% 100, H% 200
    await (root.host as RpControlbarLike).updateComplete;
    commit(field(root, "W%"), 2);
    await settle();
    const p = app.state.pieces[0].placement;
    expect([p.scale, p.scale_y]).toEqual([2, 4]);
  });

  it("with the link on, editing H% of a stretched drawing scales both", async () => {
    const { app, root } = await selected();
    await app.setScale(1, 2);
    await (root.host as RpControlbarLike).updateComplete;
    commit(field(root, "H%"), 1);
    await settle();
    const p = app.state.pieces[0].placement;
    expect([p.scale, p.scale_y]).toEqual([0.5, 1]);
  });

  it("locks the drawing's numbers while a plot runs", async () => {
    const { app, root } = await selected();
    app.onEvent("plot_state", { ...app.state.plot, state: "plotting" });
    await settle();
    for (const label of ["X", "Y", "W", "H", "Scale", "Angle"]) {
      expect(field(root, label).disabled).toBe(true);
      expect(field(root, label).tip).toBe("A plot is running.");
    }
  });

  it("asks for one drawing to resize several", async () => {
    const { app, root } = await selected();
    await app.placeJob("job-1");
    app.selectAll();
    await settle();
    expect(root.textContent).toContain("2 drawings");
    expect(field(root, "W").disabled).toBe(true);
    expect(field(root, "W").tip).toBe("Select one drawing to resize or turn it.");
  });
});
