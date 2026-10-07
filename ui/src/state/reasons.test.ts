import { describe, expect, it } from "vitest";
import { disabledReason } from "./reasons";
import { initialState, type AppState } from "./store";
import type { MachineState } from "../bridge/contract";

function state(machine: MachineState, change: Partial<AppState> = {}): AppState {
  const s = initialState();
  s.machine = { ...s.machine, state: machine, power_ok: machine !== "no_plotter" };
  return { ...s, ...change };
}

const placed = { pieces: [{ id: "p1", job_id: "j", placement: { x: 0, y: 0, scale: 1, scale_y: 1, rotation: 0 } }] };

describe("disabled reasons", () => {
  it("explains Start in the spec's order", () => {
    expect(disabledReason("start", state("no_plotter"))).toMatch(/^No plotter connected/);
    expect(disabledReason("start", state("needs_model"))).toMatch(/^Model unknown/);
    const unpowered = state("ready");
    unpowered.machine.power_ok = false;
    expect(disabledReason("start", unpowered)).toMatch(/power adapter/);
    expect(disabledReason("start", state("not_homed"))).toMatch(/^Home not set/);
    expect(disabledReason("start", state("ready"))).toMatch(/^Nothing placed/);
    const allHidden = state("ready", { ...placed, colors: [{ layer: null, color: "#000000", name: "black", lines: 1, visible: false }] });
    expect(disabledReason("start", allHidden)).toMatch(/No pens are turned on/);
  });

  it("allows moves only once homed and not plotting", () => {
    expect(disabledReason("move", state("not_homed"))).toMatch(/^Home not set/);
    expect(disabledReason("move", state("ready"))).toBeNull();
    expect(disabledReason("move", state("plotting"))).toMatch(/plot is running/);
  });

  it("needs a selection to arrange", () => {
    expect(disabledReason("arrange", state("no_plotter"))).toMatch(/^Select a drawing/);
    expect(disabledReason("arrange", state("no_plotter", { selection: ["p1"] }))).toBeNull();
  });

  it("lets the paper turn unless a plot is running", () => {
    expect(disabledReason("rotatePaper", state("no_plotter"))).toBeNull();
    expect(disabledReason("rotatePaper", state("ready", { plot: { ...initialState().plot, state: "plotting" } }))).toMatch(/plot is running/);
  });

  it("needs Home to mark the paper's corner", () => {
    expect(disabledReason("markCorner", state("not_homed"))).toMatch(/^Home not set/);
    expect(disabledReason("markCorner", state("ready"))).toBeNull();
  });

  it("needs a plotter to set Home", () => {
    expect(disabledReason("setHome", state("no_plotter"))).toMatch(/^No plotter/);
    expect(disabledReason("setHome", state("not_homed"))).toBeNull();
  });
});
