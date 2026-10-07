import { describe, expect, it } from "vitest";
import { fitCamera, MAX_SCALE, MIN_SCALE, panBy, toMachine, toScreen, zoomAt } from "./camera";

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
