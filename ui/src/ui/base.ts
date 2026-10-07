import { LitElement } from "lit";
import type { App } from "../app/app";
import { currentApp } from "../app/context";
import { StoreController, type AppState } from "../state/store";

/** A component that follows the app's state and acts through the App. */
export class AppElement extends LitElement {
  protected readonly app: App = currentApp();

  constructor() {
    super();
    new StoreController(this, this.app.store);
  }

  protected get s(): AppState {
    return this.app.store.state;
  }
}
