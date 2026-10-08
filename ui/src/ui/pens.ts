/** The Pens panel (spec §2.5): pen colors in plot order; the eye skips one in this plot. */
import { css, html, nothing } from "lit";
import { AppElement } from "./base";
import { icon } from "./icons";
import { controls } from "./styles";

export const SHOWN_PENS = 12;
export const MANY_PENS = 10;

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export class RpPens extends AppElement {
  static styles = [
    controls,
    css`
      :host {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .row {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .row.off .name {
        color: var(--text-faint);
      }
      .eye,
      .eye[aria-pressed] {
        background: none;
        border-color: transparent;
        color: var(--text);
      }
      .swatch {
        width: 12px;
        height: 12px;
        border-radius: 2px;
        border: 1px solid var(--line);
      }
      .empty,
      .more {
        color: var(--text-faint);
      }
      .warn {
        color: var(--warning);
      }
    `,
  ];

  render() {
    const colors = this.s.colors;
    if (colors.length === 0) return html`<div class="empty">Pen colors appear here once drawings are on the paper.</div>`;
    const visible = colors.filter((c) => c.visible).length;
    return html`${colors.slice(0, SHOWN_PENS).map(
        (c) => html`<div class="row ${c.visible ? "" : "off"}">
          <button
            class="icon eye"
            aria-label=${`Plot the ${c.name} pen`}
            aria-pressed=${String(c.visible)}
            @click=${() => this.app.setPenVisible(c.color, !c.visible)}
          >
            ${icon(c.visible ? "eye" : "eyeOff")}
          </button>
          <span class="swatch" style=${`background: ${c.color}`}></span>
          <span class="name">${c.layer ?? "–"} ${capitalize(c.name)}</span>
        </div>`,
      )}
      ${colors.length > SHOWN_PENS ? html`<div class="more">+${colors.length - SHOWN_PENS} more</div>` : nothing}
      ${visible >= MANY_PENS ? html`<div class="warn">${visible} pen colors: you'll change pens ${visible - 1} times.</div>` : nothing}`;
  }
}

customElements.define("rp-pens", RpPens);
