import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HOLD_DELAY_MS, HOLD_MOVE_MM } from "./app";
import { startApp } from "../test/setup";

async function homedApp() {
  const started = await startApp();
  await started.app.setHome();
  await started.app.setHome();
  // Count how many jogs are on their way at once (each takes 40 ms on this pretend plotter).
  const fake = started.fake;
  const real = fake.plotter_jog.bind(fake);
  let inFlight = 0;
  let most = 0;
  fake.plotter_jog = async (dx: number, dy: number) => {
    inFlight += 1;
    most = Math.max(most, inFlight);
    await new Promise((done) => setTimeout(done, 40));
    try {
      return await real(dx, dy);
    } finally {
      inFlight -= 1;
    }
  };
  return { ...started, mostAtOnce: () => most };
}

describe("hold a jog arrow", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("a tap moves one step", async () => {
    const { app, fake } = await homedApp();
    app.jogHold(1, 0);
    app.jogRelease();
    await vi.advanceTimersByTimeAsync(1000);
    expect(fake.called("plotter_jog")).toEqual([[1, 0]]);
  });

  it("holding keeps moving, one move at a time, until release", async () => {
    const { app, fake, mostAtOnce } = await homedApp();
    app.jogHold(1, 0);
    await vi.advanceTimersByTimeAsync(HOLD_DELAY_MS + 40 * 6);
    const jogs = fake.called("plotter_jog");
    expect(jogs.length).toBeGreaterThan(2);
    expect(jogs[0]).toEqual([1, 0]);
    expect(jogs.slice(1).every(([dx, dy]) => dx === HOLD_MOVE_MM && dy === 0)).toBe(true);
    expect(mostAtOnce()).toBe(1);
    app.jogRelease();
    const sent = fake.called("plotter_jog").length;
    await vi.advanceTimersByTimeAsync(1000);
    expect(fake.called("plotter_jog").length).toBeLessThanOrEqual(sent + 1); // only the one on its way finishes
  });

  it("holds in screen directions", async () => {
    const { app, fake } = await homedApp();
    await app.setPlotterOrientation("ne-v"); // screen right = machine -Y
    await app.movePenTo([50, 50]);
    app.jogHold(1, 0);
    await vi.advanceTimersByTimeAsync(HOLD_DELAY_MS + 100);
    app.jogRelease();
    expect(fake.called("plotter_jog").at(-1)).toEqual([0, -HOLD_MOVE_MM]);
  });

  it("stops by itself at the reach", async () => {
    const { app, fake } = await homedApp();
    await app.movePenTo([5000, 0]); // clamped to the far end of X
    app.jogHold(1, 0);
    await vi.advanceTimersByTimeAsync(3000);
    expect(fake.called("plotter_jog").length).toBeLessThanOrEqual(2);
    app.jogRelease();
  });

  it("does nothing before Home", async () => {
    const { app, fake } = await startApp();
    app.jogHold(1, 0);
    await vi.advanceTimersByTimeAsync(1000);
    app.jogRelease();
    expect(fake.called("plotter_jog")).toEqual([]);
  });
});
