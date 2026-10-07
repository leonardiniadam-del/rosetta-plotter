/** Shared setup for UI tests: an App over FakeApi, mounting components, waiting for async work. */
import { afterEach } from "vitest";
import { App } from "../app/app";
import { setApp } from "../app/context";
import { Client } from "../bridge/client";
import { FakeApi } from "../bridge/fake";
import { initialState, Store } from "../state/store";

const running: App[] = [];

export async function startApp(fake = new FakeApi()): Promise<{ app: App; fake: FakeApi }> {
  const app = new App(new Store(initialState()), new Client(fake), { colorsDelayMs: 0, scanIntervalMs: 60_000 });
  running.push(app);
  setApp(app);
  await app.start();
  return { app, fake };
}

/** Let pending promises and zero-delay timers run. */
export const settle = (): Promise<void> => new Promise((done) => setTimeout(done, 5));

export async function mount<T extends HTMLElement>(tag: string): Promise<T> {
  const element = document.createElement(tag) as T;
  document.body.append(element);
  await (element as unknown as { updateComplete?: Promise<unknown> }).updateComplete;
  return element;
}

export function shadow(element: Element): ShadowRoot {
  if (!element.shadowRoot) throw new Error(`${element.tagName} has no shadow root`);
  return element.shadowRoot;
}

afterEach(() => {
  for (const app of running.splice(0)) app.stop();
  document.body.innerHTML = "";
});
