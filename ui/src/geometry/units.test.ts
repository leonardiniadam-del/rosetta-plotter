import { describe, expect, it } from "vitest";
import {
  formatAngle,
  formatLength,
  formatPercent,
  normalizeAngle,
  parseAngle,
  parseLength,
  parsePercent,
  toUnits,
} from "./units";

describe("lengths", () => {
  it("formats in each unit", () => {
    expect(formatLength(82.6, "in")).toBe("3.25");
    expect(formatLength(82.6, "mm", true)).toBe("82.6 mm");
    expect(formatLength(82.6, "cm")).toBe("8.26");
  });

  it("never shows minus zero", () => {
    expect(formatLength(-0.001, "mm")).toBe("0.0");
  });

  it("reads typed lengths with or without a unit", () => {
    expect(parseLength("2", "in")).toBeCloseTo(50.8);
    expect(parseLength('2"', "mm")).toBeCloseTo(50.8);
    expect(parseLength("2 inches", "mm")).toBeCloseTo(50.8);
    expect(parseLength("50mm", "in")).toBeCloseTo(50);
    expect(parseLength(" 5 cm ", "in")).toBeCloseTo(50);
    expect(parseLength(".5", "cm")).toBeCloseTo(5);
    expect(parseLength("-3", "mm")).toBeCloseTo(-3);
  });

  it("refuses what it can't read", () => {
    for (const text of ["", "abc", "2 ft", "1/2", "1e400", "2..5"]) {
      expect(parseLength(text, "in")).toBeNull();
    }
  });

  it("converts", () => {
    expect(toUnits(25.4, "in")).toBe(1);
    expect(toUnits(25.4, "cm")).toBeCloseTo(2.54);
  });
});

describe("percent and angles", () => {
  it("reads percentages", () => {
    expect(parsePercent("50")).toBe(0.5);
    expect(parsePercent("12.5%")).toBe(0.125);
    expect(parsePercent("0")).toBeNull();
    expect(parsePercent("30°")).toBeNull();
  });

  it("reads angles and wraps them into one turn", () => {
    expect(parseAngle("30°")).toBe(30);
    expect(parseAngle("-90")).toBe(270);
    expect(parseAngle("450")).toBe(90);
    expect(parseAngle("50%")).toBeNull();
    expect(normalizeAngle(-0)).toBe(0);
    expect(Object.is(normalizeAngle(-360), 0)).toBe(true);
  });

  it("formats", () => {
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(1.2346)).toBe("123.5%");
    expect(formatAngle(-30)).toBe("330°");
    expect(formatAngle(359.97)).toBe("0°");
  });
});
