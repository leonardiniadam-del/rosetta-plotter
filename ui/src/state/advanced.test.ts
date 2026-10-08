import { describe, expect, it } from "vitest";
import { FAKE_ADVANCED } from "../bridge/fake";
import { changedAdvanced, checkAdvanced } from "./advanced";

const options = {
  labels: { accel: "Acceleration", pen_up: "Pen-up height", reordering: "Path order", hiding: "Hidden-line removal" },
  ranges: { accel: [1, 100] as [number, number], pen_up: [0, 100] as [number, number] },
  choices: { reordering: [0, 1, 2, 4] },
  defaults: FAKE_ADVANCED,
};

describe("Advanced options", () => {
  it("are checked in the page, with Python's wording", () => {
    expect(checkAdvanced({ accel: 60, pen_up: null, hiding: true, reordering: 4 }, options)).toBeNull();
    expect(checkAdvanced({ accel: 500 }, options)).toBe("Acceleration must be from 1 to 100.");
    expect(checkAdvanced({ accel: 2.5 }, options)).toBe("Acceleration must be a whole number.");
    expect(checkAdvanced({ accel: Number.NaN }, options)).toBe("Acceleration must be a whole number.");
    expect(checkAdvanced({ accel: null }, options)).toBe("Acceleration must be a whole number.");
    expect(checkAdvanced({ reordering: 3 }, options)).toBe("Path order must be one of 0, 1, 2, 4.");
    expect(checkAdvanced({ hiding: 1 }, options)).toBe("Hidden-line removal must be on or off.");
  });

  it("send only what changed", () => {
    expect(changedAdvanced({ ...FAKE_ADVANCED, accel: 60 }, FAKE_ADVANCED)).toEqual({ accel: 60 });
  });
});
