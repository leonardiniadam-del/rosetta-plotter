/** The running App, for components to act through (set once at start-up, and by each test). */
import type { App } from "./app";

let current: App | null = null;

export function setApp(app: App): void {
  current = app;
}

export function currentApp(): App {
  if (!current) throw new Error("The app hasn't started.");
  return current;
}
