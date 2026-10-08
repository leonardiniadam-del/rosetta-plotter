import { afterEach, describe, expect, it } from "vitest";
import { BridgeError, Client, insideApp, listenForEvents, waitForApi } from "./client";
import type { Api } from "./contract";

type Global = Window & { pywebview?: unknown; rosettaEvent?: (name: string, data: unknown) => void };

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => (resolve = done));
  return { promise, resolve };
}

const tick = () => new Promise((done) => setTimeout(done, 0));

describe("Client", () => {
  it("returns ok replies and throws BridgeError for problems", async () => {
    const api = {
      set_units: async () => ({ ok: true }),
      artwork_pages: async () => ({ ok: false, message: "That file can't be found.", details: "FileNotFoundError" }),
    } as unknown as Api;
    const client = new Client(api);
    await expect(client.call("set_units", "mm")).resolves.toEqual({ ok: true });
    const error = await client.call("artwork_pages", "x.svg").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(BridgeError);
    expect([(error as BridgeError).message, (error as BridgeError).details]).toEqual([
      "That file can't be found.",
      "FileNotFoundError",
    ]);
  });

  it("runs plotter calls one at a time, even after a failure", async () => {
    const log: string[] = [];
    const gate = deferred();
    const api = {
      plotter_jog: async (dx: number) => {
        log.push(`start ${dx}`);
        if (dx === 1) await gate.promise;
        log.push(`end ${dx}`);
        return dx === 1 ? { ok: false, message: "busy", details: "" } : { ok: true, machine: {} };
      },
    } as unknown as Api;
    const client = new Client(api);
    const first = client.hardware("plotter_jog", 1, 0).catch(() => "failed");
    const second = client.hardware("plotter_jog", 2, 0);
    await tick();
    expect(log).toEqual(["start 1"]);
    gate.resolve();
    expect(await first).toBe("failed");
    await second;
    expect(log).toEqual(["start 1", "end 1", "start 2", "end 2"]);
  });

  it("keeps only the newest waiting slider value", async () => {
    const sent: number[] = [];
    const gate = deferred();
    const api = {
      pen_set: async (down: number) => {
        sent.push(down);
        if (down === 10) await gate.promise;
        return { ok: true, machine: { pen_down: down } };
      },
    } as unknown as Api;
    const client = new Client(api);
    const first = client.latest("pen", "pen_set", 10, "fineliner");
    const skipped = client.latest("pen", "pen_set", 20, "fineliner");
    const last = client.latest("pen", "pen_set", 30, "fineliner");
    await expect(skipped).resolves.toBeNull();
    gate.resolve();
    await first;
    expect(await last).toMatchObject({ ok: true });
    expect(sent).toEqual([10, 30]);
  });
});

describe("window bridge", () => {
  afterEach(() => {
    delete (window as Global).pywebview;
  });

  it("finds the bridge once pywebview injects it", async () => {
    const api = { app_start: () => undefined } as unknown as Api;
    const pending = waitForApi(1000);
    (window as Global).pywebview = { api };
    window.dispatchEvent(new Event("pywebviewready"));
    await expect(pending).resolves.toBe(api);
  });

  it("waitForApi waits until the bridge has its methods", async () => {
    const w = window as unknown as { pywebview?: { api?: object } };
    w.pywebview = { api: {} };
    const waiting = waitForApi(1000);
    setTimeout(() => (w.pywebview = { api: { app_start: () => undefined } }), 60);
    const api = await waiting;
    expect(typeof (api as unknown as { app_start: unknown }).app_start).toBe("function");
    delete w.pywebview;
  });

  it("tells the app's window from a plain browser", () => {
    expect(insideApp()).toBe(false);
    (window as Global).pywebview = {};
    expect(insideApp()).toBe(true);
  });

  it("gives up after the timeout", async () => {
    await expect(waitForApi(10)).rejects.toThrow("didn't answer");
  });

  it("receives Python's events", () => {
    const seen: unknown[] = [];
    listenForEvents((name, data) => seen.push([name, data]));
    (window as Global).rosettaEvent?.("plot_state", { state: "ready" });
    expect(seen).toEqual([["plot_state", { state: "ready" }]]);
  });
});
