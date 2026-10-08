import { describe, expect, it } from "vitest";
import { formatDuration, overallFraction } from "./plotting";

describe("plot helpers", () => {
  it("formats durations as m:ss, or h:mm:ss", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(59.6)).toBe("1:00");
    expect(formatDuration(250)).toBe("4:10");
    expect(formatDuration(3725)).toBe("1:02:05");
  });

  it("works out how far through the whole plot it is", () => {
    expect(overallFraction(100, null)).toBe(0);
    expect(overallFraction(100, { layer: 0, x: 0, y: 0, pendown_mm: 0, fraction: 0.5, seconds_left: 25 })).toBe(0.75);
    expect(overallFraction(0, { layer: 0, x: 0, y: 0, pendown_mm: 0, fraction: 1, seconds_left: 0 })).toBe(1);
  });
});
