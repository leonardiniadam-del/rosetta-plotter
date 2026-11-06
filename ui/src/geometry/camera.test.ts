import { describe, expect, it } from "vitest";
import { cameraMatrix, fitCamera, MAX_SCALE, MIN_SCALE, panBy, toMachine, toScreen, zoomAt } from "./camera";
import { orientMatrix, ORIENTATIONS } from "./orientation";

describe("camera", () => {
  it("fits a box in the view, centered", () => {
    const camera = fitCamera({ x: 0, y: 0, width: 200, height: 100 }, { width: 464, height: 300 }, 32);
    expect(camera.scale).toBe(2);
    expect(toScreen(camera, [0, 0])).toEqual([32, 50]);
    expect(toScreen(camera, [200, 100])).toEqual([432, 250]);
  });

  it("maps screen and machine both ways", () => {
    const camera = { scale: 3, x: 10, y: -5 };
    expect(toMachine(camera, toScreen(camera, [12.5, 7]))).toEqual([12.5, 7]);
  });

  it("zooms about the cursor", () => {
    const camera = { scale: 2, x: 10, y: 20 };
    const zoomed = zoomAt(camera, 1.5, [110, 120]);
    expect(zoomed.scale).toBe(3);
    expect(toMachine(zoomed, [110, 120])).toEqual(toMachine(camera, [110, 120]));
  });

  it("keeps the zoom within limits", () => {
    expect(zoomAt({ scale: 1, x: 0, y: 0 }, 1e9, [0, 0]).scale).toBe(MAX_SCALE);
    expect(zoomAt({ scale: 1, x: 0, y: 0 }, 1e-9, [0, 0]).scale).toBe(MIN_SCALE);
  });

  it("pans", () => {
    expect(panBy({ scale: 1, x: 0, y: 0 }, 5, -3)).toEqual({ scale: 1, x: 5, y: -3 });
  });
});

describe("oriented camera", () => {
  it.each(ORIENTATIONS)("%s round-trips points", (code) => {
    const camera = { scale: 2.5, x: 40, y: 70, orient: orientMatrix(code) };
    const [x, y] = toMachine(camera, toScreen(camera, [12.5, -3]));
    expect(x).toBeCloseTo(12.5, 9);
    expect(y).toBeCloseTo(-3, 9);
  });

  it("fits a turned box: 100 across, 200 down", () => {
    const camera = fitCamera({ x: 0, y: 0, width: 200, height: 100 }, { width: 400, height: 800 }, 32, orientMatrix("nw-v"));
    expect(camera.scale).toBe(Math.min((400 - 64) / 100, (800 - 64) / 200));
    const a = toScreen(camera, [0, 0]);
    const b = toScreen(camera, [200, 100]);
    expect((a[0] + b[0]) / 2).toBeCloseTo(200, 9);
    expect((a[1] + b[1]) / 2).toBeCloseTo(400, 9);
  });

  it("keeps its orientation when zoomed and panned", () => {
    const camera = { scale: 2, x: 0, y: 0, orient: orientMatrix("se-h") };
    expect(zoomAt(camera, 2, [5, 5]).orient).toEqual(camera.orient);
    expect(panBy(camera, 1, 1).orient).toEqual(camera.orient);
  });

  it("gives the SVG matrix", () => {
    expect(cameraMatrix({ scale: 2, x: 10, y: 20, orient: orientMatrix("ne-h") })).toBe("matrix(-2 0 0 2 10 20)");
    expect(cameraMatrix({ scale: 2, x: 10, y: 20 })).toBe("matrix(2 0 0 2 10 20)");
  });
});
