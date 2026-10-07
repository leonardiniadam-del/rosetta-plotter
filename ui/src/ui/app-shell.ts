/**
 * The manager window (spec §2): menu bar, control bar, tools on the left, the plate in the middle with the
 * notification strip over it, the dock of panels on the right, and the status bar.
 */
import { css, html, LitElement } from "lit";
import "./controlbar";
import "./dialogs";
import "./plate";
import "./statusbar";
import "./strip";
import "./tools";

export class RpApp extends LitElement {
  static styles = css`
    :host {
      display: grid;
      grid-template-rows: 26px 34px minmax(0, 1fr) 24px;
      height: 100%;
      background: var(--app-bg);
    }
    .main {
      display: grid;
      grid-template-columns: 40px minmax(0, 1fr) 220px;
      min-height: 0;
    }
    .center {
      position: relative;
      display: flex;
      min-width: 0;
      min-height: 0;
    }
    rp-plate {
      flex: 1;
    }
    rp-strip {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      z-index: 5;
    }
    rp-menubar,
    rp-controlbar {
      background: var(--panel);
      border-bottom: 1px solid var(--line);
    }
    rp-statusbar {
      background: var(--panel);
      border-top: 1px solid var(--line);
    }
    rp-tools {
      background: var(--panel);
      border-right: 1px solid var(--line);
    }
    rp-dock {
      min-height: 0;
      background: var(--panel);
      border-left: 1px solid var(--line);
    }
  `;

  render() {
    return html`<rp-menubar></rp-menubar>
      <rp-controlbar></rp-controlbar>
      <div class="main">
        <rp-tools></rp-tools>
        <div class="center">
          <rp-plate></rp-plate>
          <rp-strip></rp-strip>
        </div>
        <rp-dock></rp-dock>
      </div>
      <rp-statusbar></rp-statusbar>
      <rp-dialogs></rp-dialogs>`;
  }
}

customElements.define("rp-app", RpApp);
