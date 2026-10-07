import { describe, expect, it } from "vitest";
import "./field";
import { mount, shadow } from "../test/setup";
import type { RpField } from "./field";

async function field(props: Partial<RpField>) {
  const element = await mount<RpField>("rp-field");
  Object.assign(element, props);
  await element.updateComplete;
  const input = shadow(element).querySelector("input") as HTMLInputElement;
  const commits: number[] = [];
  element.addEventListener("commit", (e) => commits.push((e as CustomEvent<number>).detail));
  return { element, input, commits };
}

describe("rp-field", () => {
  it("leaving the box without typing commits nothing, even when the shown value is rounded", async () => {
    const { input, commits } = await field({ value: 10.123, units: "in" });
    input.dispatchEvent(new FocusEvent("focus"));
    input.dispatchEvent(new FocusEvent("blur"));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    expect(commits).toEqual([]);
  });

  it("commits what was typed", async () => {
    const { input, commits } = await field({ value: 10, units: "mm" });
    input.value = "1 in";
    input.dispatchEvent(new FocusEvent("blur"));
    expect(commits).toEqual([25.4]);
  });

  it("a read-only box never commits and shows its value again", async () => {
    const { input, commits } = await field({ value: 297, units: "mm", readonly: true });
    input.value = "5";
    input.dispatchEvent(new FocusEvent("blur"));
    expect(commits).toEqual([]);
    expect(input.value).toBe("297.0");
  });
});
