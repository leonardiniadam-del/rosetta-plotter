import { describe, expect, it } from "vitest";
import { FAKE_MODELS } from "../bridge/fake";
import { initialState, Store, StoreController } from "./store";
import { pieceBoxOnPaper, plotRunning, reachOf, selectionBox } from "./selectors";
import type { AppStart, JobInfo } from "../bridge/contract";

const job = { id: "job-1", width_mm: 40, height_mm: 20 } as JobInfo;

describe("Store", () => {
  it("merges changes and tells subscribers", () => {
    const store = new Store({ a: 1, b: 2 });
    const seen: number[] = [];
    const stop = store.subscribe(() => seen.push(store.state.a));
    store.update({ a: 5 });
    store.update((s) => ({ a: s.a + 1 }));
    stop();
    store.update({ a: 9 });
    expect(seen).toEqual([5, 6]);
    expect(store.state).toEqual({ a: 9, b: 2 });
  });

  it("asks a Lit host to re-render while it's connected", () => {
    const store = new Store({ n: 0 });
    let updates = 0;
    const host = { addController() {}, removeController() {}, requestUpdate: () => (updates += 1), updateComplete: Promise.resolve(true) };
    const controller = new StoreController(host, store);
    controller.hostConnected();
    store.update({ n: 1 });
    controller.hostDisconnected();
    store.update({ n: 2 });
    expect(updates).toBe(1);
  });
});

describe("selectors", () => {
  it("finds the plotter's reach from its model", () => {
    const state = initialState();
    expect(reachOf(state)).toBeNull();
    state.start = { models: FAKE_MODELS } as AppStart;
    state.machine = { ...state.machine, state: "ready", model: 1 };
    expect(reachOf(state)).toEqual([299.974, 217.932]);
  });

  it("boxes the selection", () => {
    const state = initialState();
    state.jobs = [job];
    state.pieces = [
      { id: "p1", job_id: "job-1", placement: { x: 0, y: 0, scale: 1, scale_y: 1, rotation: 0 } },
      { id: "p2", job_id: "job-1", placement: { x: 100, y: 50, scale: 2, scale_y: 1, rotation: 90 } },
    ];
    expect(pieceBoxOnPaper(state, state.pieces[1])).toEqual({ x: 100, y: 50, width: 20, height: 80 });
    state.selection = ["p1", "p2"];
    expect(selectionBox(state)).toEqual({ x: 0, y: 0, width: 120, height: 130 });
  });

  it("knows when a plot is running", () => {
    const state = initialState();
    expect(plotRunning(state)).toBe(false);
    state.plot = { ...state.plot, state: "paused" };
    expect(plotRunning(state)).toBe(true);
  });
});
