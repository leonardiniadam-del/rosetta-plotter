import { describe, expect, it } from "vitest";
import {
  codeFromPicks,
  DEFAULT_ORIENTATION,
  machineToScreenDir,
  neighbours,
  orientMatrix,
  ORIENTATIONS,
  screenToMachineDir,
  type OrientationCode,
} from "./orientation";

// Machine +X and +Y as screen directions (orientation plan, Task 2 table).
const TABLE: Record<OrientationCode, [[number, number], [number, number]]> = {
  "nw-h": [[1, 0], [0, 1]],
  "nw-v": [[0, 1], [1, 0]],
  "ne-h": [[-1, 0], [0, 1]],
  "ne-v": [[0, 1], [-1, 0]],
  "se-h": [[-1, 0], [0, -1]],
  "se-v": [[0, -1], [-1, 0]],
  "sw-h": [[1, 0], [0, -1]],
  "sw-v": [[0, -1], [1, 0]],
};

const plain = ([x, y]: [number, number]) => [x + 0, y + 0];

describe("plate orientations", () => {
  it("has the eight, standard first", () => {
    expect(ORIENTATIONS).toEqual(["nw-h", "nw-v", "ne-h", "ne-v", "se-h", "se-v", "sw-h", "sw-v"]);
    expect(DEFAULT_ORIENTATION).toBe("nw-h");
  });

  it.each(ORIENTATIONS)("%s maps machine X and Y as the table says", (code) => {
    const o = orientMatrix(code);
    expect(plain(machineToScreenDir(o, [1, 0]))).toEqual(TABLE[code][0]);
    expect(plain(machineToScreenDir(o, [0, 1]))).toEqual(TABLE[code][1]);
  });

  it.each(ORIENTATIONS)("%s puts Home in its corner", (code) => {
    const o = orientMatrix(code);
    const corners = ([[0, 0], [100, 0], [100, 50], [0, 50]] as [number, number][]).map((p) => machineToScreenDir(o, p));
    const [hx, hy] = corners[0];
    const xs = corners.map((c) => c[0]);
    const ys = corners.map((c) => c[1]);
    expect(hx).toBe(code[1] === "w" ? Math.min(...xs) : Math.max(...xs));
    expect(hy).toBe(code[0] === "n" ? Math.min(...ys) : Math.max(...ys));
  });

  it.each(ORIENTATIONS)("%s: h means machine X runs across the screen", (code) => {
    expect(machineToScreenDir(orientMatrix(code), [1, 0])[0] !== 0).toBe(code.endsWith("-h"));
  });

  it.each(ORIENTATIONS)("%s round-trips directions", (code) => {
    const o = orientMatrix(code);
    expect(plain(screenToMachineDir(o, machineToScreenDir(o, [3, -7])))).toEqual([3, -7]);
  });

  it("turns two picked corners into a code", () => {
    expect(codeFromPicks("ne", "se")).toBe("ne-v");
    expect(codeFromPicks("sw", "se")).toBe("sw-h");
    expect(codeFromPicks("nw", "ne")).toBe("nw-h");
    expect(codeFromPicks("nw", "se")).toBeNull();
    expect(codeFromPicks("nw", "nw")).toBeNull();
  });

  it("knows each corner's neighbours", () => {
    expect(neighbours("nw").sort()).toEqual(["ne", "sw"]);
    expect(neighbours("se").sort()).toEqual(["ne", "sw"]);
  });
});
