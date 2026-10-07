/** Talking to Python through pywebview (docs/bridge.md). */
import type { Api } from "./contract";

/** A problem Python reported: `message` is for the student as written, `details` for the Details link. */
export class BridgeError extends Error {
  readonly details: string;

  constructor(message: string, details = "") {
    super(message);
    this.name = "BridgeError";
    this.details = details;
  }
}

export type Method = keyof Api;
export type Args<M extends Method> = Parameters<Api[M]>;
export type Ok<M extends Method> = Extract<Awaited<ReturnType<Api[M]>>, { ok: true }>;

type AnyCall = (method: Method, ...args: unknown[]) => Promise<unknown>;
type Slot = { method: Method; args: unknown[]; resolve: (value: unknown) => void; reject: (error: unknown) => void };

/**
 * call(): one bridge call; {ok: false} becomes a BridgeError.
 * hardware(): plotter requests run one at a time (Python answers a second one with "still busy").
 * latest(): like hardware(), but while one runs only the newest waiting call for the same key is kept;
 * the calls it replaces resolve to null. The pen-height slider uses it.
 */
export class Client {
  private chain: Promise<unknown> = Promise.resolve();
  private readonly slots = new Map<string, Slot>();
  private readonly draining = new Set<string>();

  constructor(private readonly api: Api) {}

  async call<M extends Method>(method: M, ...args: Args<M>): Promise<Ok<M>> {
    const fn = this.api[method] as unknown as (...a: unknown[]) => Promise<{ ok: boolean; message?: string; details?: string }>;
    const reply = await fn.apply(this.api, args);
    if (!reply.ok) throw new BridgeError(reply.message ?? "", reply.details ?? "");
    return reply as Ok<M>;
  }

  hardware<M extends Method>(method: M, ...args: Args<M>): Promise<Ok<M>> {
    const run = this.chain.then(() => this.call(method, ...args));
    this.chain = run.catch(() => undefined);
    return run;
  }

  latest<M extends Method>(key: string, method: M, ...args: Args<M>): Promise<Ok<M> | null> {
    return new Promise((resolve, reject) => {
      this.slots.get(key)?.resolve(null);
      this.slots.set(key, { method, args, resolve: resolve as (value: unknown) => void, reject });
      if (!this.draining.has(key)) void this.drain(key);
    });
  }

  private async drain(key: string): Promise<void> {
    this.draining.add(key);
    const hardware = this.hardware.bind(this) as unknown as AnyCall;
    try {
      for (let slot = this.slots.get(key); slot; slot = this.slots.get(key)) {
        this.slots.delete(key);
        try {
          slot.resolve(await hardware(slot.method, ...slot.args));
        } catch (error) {
          slot.reject(error);
        }
      }
    } finally {
      this.draining.delete(key);
    }
  }
}

type PyWindow = Window & {
  pywebview?: { api?: Api };
  rosettaEvent?: (name: string, data: unknown) => void;
};

/** The real bridge, once pywebview has injected it. Rejects after timeoutMs (in a plain browser, say). */
export function waitForApi(timeoutMs: number): Promise<Api> {
  const w = window as PyWindow;
  return new Promise((resolve, reject) => {
    if (w.pywebview?.api) {
      resolve(w.pywebview.api);
      return;
    }
    const timer = window.setTimeout(() => reject(new Error("The app's Python side didn't answer.")), timeoutMs);
    window.addEventListener(
      "pywebviewready",
      () => {
        window.clearTimeout(timer);
        if (w.pywebview?.api) resolve(w.pywebview.api);
        else reject(new Error("The app's Python side didn't answer."));
      },
      { once: true },
    );
  });
}

/** Python calls window.rosettaEvent(name, data): plot states, progress, dropped files, closing mid-plot. */
export function listenForEvents(handler: (name: string, data: unknown) => void): void {
  (window as PyWindow).rosettaEvent = handler;
}
