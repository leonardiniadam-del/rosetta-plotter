/** Start the page: find Python's bridge (or the demo FakeApi under `npm run dev`), then mount the window. */
import "./theme.css";
import "./ui/app-shell";
import { App } from "./app/app";
import { setApp } from "./app/context";
import { Client, listenForEvents, waitForApi } from "./bridge/client";
import type { Api } from "./bridge/contract";
import { FakeApi } from "./bridge/fake";
import { installShortcuts } from "./shortcuts";
import { initialState, Store } from "./state/store";

async function pickApi(): Promise<Api> {
  try {
    return await waitForApi(import.meta.env.DEV ? 1500 : 15000);
  } catch (error) {
    if (import.meta.env.DEV) return new FakeApi(); // a plain browser: run against the demo backend
    throw error;
  }
}

async function boot(): Promise<void> {
  const app = new App(new Store(initialState()), new Client(await pickApi()));
  setApp(app);
  listenForEvents((name, data) => app.onEvent(name, data));
  installShortcuts(app);
  document.body.append(document.createElement("rp-app"));
  await app.start();
  (window as Window & { rosettaReady?: boolean }).rosettaReady = true;
}

boot().catch((error: unknown) => {
  document.body.textContent = `Rosetta Plotter couldn't start: ${error instanceof Error ? error.message : String(error)}`;
});
