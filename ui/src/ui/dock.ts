/** The dock on the right (spec §2.5): Jobs, Pens and Plotter panels, each collapsible. */
import { css, html, LitElement, nothing } from "lit";
import { icon } from "./icons";
import "./jobs";
import "./pens";
import "./plotter-panel";
import { controls } from "./styles";

export class RpDock extends LitElement {
  static properties = { collapsed: { state: true } };

  static styles = [
    controls,
    css`
      :host {
        display: flex;
        flex-direction: column;
        overflow-y: auto;
      }
      section {
        border-bottom: 1px solid var(--line);
      }
      h2 {
        display: flex;
        margin: 0;
        font: inherit;
      }
      h2 button {
        flex: 1;
        justify-content: space-between;
        height: 26px;
        font-weight: 600;
        background: var(--panel-raised);
        border: none;
        border-radius: 0;
      }
      h2 button[aria-expanded="false"] svg {
        transform: rotate(-90deg);
      }
      .body {
        padding: 6px 8px;
      }
      section.jobs .body {
        max-height: 40vh;
        overflow-y: auto;
      }
    `,
  ];

  declare collapsed: Set<string>;

  constructor() {
    super();
    this.collapsed = new Set();
  }

  private toggle(name: string): void {
    const next = new Set(this.collapsed);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    this.collapsed = next;
  }

  private panel(name: string, title: string, body: unknown) {
    const open = !this.collapsed.has(name);
    return html`<section class=${name}>
      <h2><button aria-expanded=${String(open)} @click=${() => this.toggle(name)}>${title}${icon("chevronDown")}</button></h2>
      ${open ? html`<div class="body">${body}</div>` : nothing}
    </section>`;
  }

  render() {
    return html`${this.panel("jobs", "Jobs", html`<rp-jobs></rp-jobs>`)}${this.panel("pens", "Pens", html`<rp-pens></rp-pens>`)}${this.panel(
      "plotter",
      "Plotter",
      html`<rp-plotter></rp-plotter>`,
    )}`;
  }
}

customElements.define("rp-dock", RpDock);
