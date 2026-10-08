/** Start the page: find Python's bridge (or the demo FakeApi under `npm run dev`), then mount the window. */
import "./theme.css";
import "./ui/app-shell";
import { App } from "./app/app";
import { setApp } from "./app/context";
import { Client, insideApp, listenForEvents, waitForApi } from "./bridge/client";
import type { Api } from "./bridge/contract";
import { FakeApi } from "./bridge/fake";
import { installShortcuts } from "./shortcuts";
import { initialState, Store } from "./state/store";

async function pickApi(): Promise<Api> {
  // pywebview creates window.pywebview before it fills the API, so insideApp() is true in the window from the start.
  const plainBrowser = import.meta.env.DEV && !insideApp();
  try {
    return await waitForApi(plainBrowser ? 1500 : 15000);
  } catch (error) {
    if (plainBrowser) return new FakeApi(); // `npm run dev` in a browser: the demo backend
    throw error;
  }
}

async function boot(): Promise<void> {
  const api = await pickApi();
  const app = new App(new Store(initialState()), new Client(api));
  if (api instanceof FakeApi) {
    api.emit = (name, data) => app.onEvent(name, data); // the demo backend's events, as Python's would arrive
    api.autoplay();
  }
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
