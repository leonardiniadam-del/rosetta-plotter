/** The notification strip across the top of the plate (spec §4.6): never a popup. */
import { css, html, nothing } from "lit";
import { AppElement } from "./base";
import { icon } from "./icons";
import { controls } from "./styles";

export class RpStrip extends AppElement {
  static properties = { open: { state: true } };

  static styles = [
    controls,
    css`
      .strip {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 8px;
        background: var(--panel-raised);
        border-bottom: 1px solid var(--line);
      }
      .error {
        border-left: 3px solid var(--danger);
      }
      .warning {
        border-left: 3px solid var(--warning);
      }
      .info {
        border-left: 3px solid var(--accent);
      }
      .message {
        flex: 1;
      }
      pre {
        margin: 0;
        padding: 8px;
        max-height: 160px;
        overflow: auto;
        white-space: pre-wrap;
        user-select: text;
        background: var(--panel);
        color: var(--text-dim);
        border-bottom: 1px solid var(--line);
      }
    `,
  ];

  declare open: boolean;

  constructor() {
    super();
    this.open = false;
  }

  render() {
    const notice = this.s.notice;
    if (!notice) return nothing;
    return html`<div class="strip ${notice.kind}" role=${notice.kind === "error" ? "alert" : "status"}>
        ${icon(notice.kind === "info" ? "info" : "alert")}
        <span class="message">${notice.message}</span>
        ${(notice.actions ?? []).map((action) => html`<button @click=${action.run}>${action.label}</button>`)}
        ${notice.details
          ? html`<button aria-expanded=${this.open ? "true" : "false"} @click=${() => (this.open = !this.open)}>Details</button>`
          : nothing}
        ${notice.kind === "error" ? html`<button @click=${() => this.app.copyDiagnostics()}>Copy diagnostics</button>` : nothing}
        <button
          class="icon"
          aria-label="Close"
          @click=${() => {
            this.open = false;
            this.app.dismissNotice();
          }}
        >
          ${icon("x")}
        </button>
      </div>
      ${this.open && notice.details ? html`<pre>${notice.details}</pre>` : nothing}`;
  }
}

customElements.define("rp-strip", RpStrip);
