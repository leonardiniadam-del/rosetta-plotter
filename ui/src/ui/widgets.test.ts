import { describe, expect, it } from "vitest";
import "./field";
import "./strip";
import "./dialogs";
import { ICON_NAMES, iconSvg } from "./icons";
import type { RpField } from "./field";
import { mount, settle, shadow, startApp } from "../test/setup";

describe("icons", () => {
  it("are all real SVGs", () => {
    for (const name of ICON_NAMES) expect(iconSvg(name)).toMatch(/^<svg class="icon" aria-hidden="true"/);
  });
});

describe("rp-field", () => {
  async function field(value: number) {
    await startApp();
    const element = await mount<RpField>("rp-field");
    element.value = value;
    element.units = "in";
    await element.updateComplete;
    const input = shadow(element).querySelector("input") as HTMLInputElement;
    const committed: number[] = [];
    element.addEventListener("commit", (e) => committed.push((e as CustomEvent<number>).detail));
    return { element, input, committed };
  }

  it("shows the value in the chosen units and reads what's typed", async () => {
    const { input, committed } = await field(50.8);
    expect(input.value).toBe("2.00");
    input.focus();
    input.value = "3 cm";
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    expect(committed).toEqual([30]);
  });

  it("puts the old value back when it can't read the new one", async () => {
    const { element, input, committed } = await field(50.8);
    input.focus();
    input.value = "lots";
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await element.updateComplete;
    expect(committed).toEqual([]);
    expect(input.value).toBe("2.00");
    expect(input.getAttribute("aria-invalid")).toBe("true");
  });
});

describe("rp-strip", () => {
  it("shows a problem with its details, and closes", async () => {
    const { app } = await startApp();
    const strip = await mount("rp-strip");
    app.notify({ kind: "error", message: "The plot stopped unexpectedly.", details: "SerialException: gone" });
    await settle();
    const root = shadow(strip);
    expect(root.textContent).toContain("The plot stopped unexpectedly.");
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Details") as HTMLButtonElement).click();
    await settle();
    expect(root.querySelector("pre")?.textContent).toBe("SerialException: gone");
    (root.querySelector('button[aria-label="Close"]') as HTMLButtonElement).click();
    await settle();
    expect(app.state.notice).toBeNull();
  });
});

describe("notification strip", () => {
  it("closes Details when a different notice arrives", async () => {
    const { app } = await startApp();
    const strip = await mount<HTMLElement & { updateComplete: Promise<unknown> }>("rp-strip");
    app.notify({ kind: "error", message: "First.", details: "trace one" });
    await strip.updateComplete;
    const details = Array.from(shadow(strip).querySelectorAll("button")).find((b) => b.textContent?.trim() === "Details") as HTMLButtonElement;
    details.click();
    await strip.updateComplete;
    expect(shadow(strip).querySelector("pre")?.textContent).toBe("trace one");
    app.notify({ kind: "error", message: "Second.", details: "trace two" });
    await strip.updateComplete;
    expect(shadow(strip).querySelector("pre")).toBeNull();
  });
});

describe("rp-dialogs", () => {
  it("asks which page", async () => {
    const { app } = await startApp();
    const dialogs = await mount("rp-dialogs");
    const answer = app.askPage("set.pdf", 3);
    await settle();
    const root = shadow(dialogs);
    expect(root.textContent).toContain("Which page of set.pdf?");
    (root.querySelector("select") as HTMLSelectElement).value = "2";
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.includes("Import page")) as HTMLButtonElement).click();
    expect(await answer).toBe(2);
  });

  it("stores the plotter's model", async () => {
    const { app, fake } = await startApp();
    const dialogs = await mount("rp-dialogs");
    app.openModelDialog();
    await settle();
    const root = shadow(dialogs);
    const two = root.querySelector('input[value="2"]') as HTMLInputElement;
    two.checked = true;
    two.dispatchEvent(new Event("change")); // as a real click does
    (root.querySelector("#label") as HTMLInputElement).value = " PSU Lab ";
    (Array.from(root.querySelectorAll("button")).find((b) => b.textContent?.trim() === "Save") as HTMLButtonElement).click();
    await settle();
    expect(fake.called("plotter_identify")).toEqual([[2, 1, "PSU Lab"]]);
    expect(app.state.dialog).toBeNull();
  });
});
