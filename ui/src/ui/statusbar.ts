/** The status bar (spec §2.6): plotter and model, power, Home, pen and cursor positions, units. */
import { css, html, nothing } from "lit";
import { live } from "lit/directives/live.js";
import { formatLength, UNITS, type Units } from "../geometry/units";
import type { Point } from "../geometry/placement";
import { plotRunning } from "../state/selectors";
import { StoreController } from "../state/store";
import { AppElement } from "./base";
import { icon } from "./icons";
import { controls } from "./styles";

export class RpStatusbar extends AppElement {
  static styles = [
    controls,
    css`
      :host {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 0 10px;
        font-size: var(--font-size-small);
        color: var(--text-dim);
      }
      span {
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      .ok {
        color: var(--success);
      }
      .bad {
        color: var(--warning);
      }
      .spacer {
        flex: 1;
      }
      select {
        height: 18px;
      }
    `,
  ];

  constructor() {
    super();
    new StoreController(this, this.app.cursor);
    new StoreController(this, this.app.progress);
  }

  render() {
    const { machine: m, units } = this.s;
    const where = (point: Point | null) => (point ? `${formatLength(point[0], units)}, ${formatLength(point[1], units)}` : "—");
    const connected = m.state !== "no_plotter";
    const name = !connected ? "No plotter" : m.state === "needs_model" ? "Model unknown" : (m.model_name ?? "AxiDraw");
    const plotting = plotRunning(this.s);
    const latest = this.app.progress.state.value;
    const pen = plotting && latest ? ([latest.x, latest.y] as Point) : m.position;
    const homeSet = m.state === "ready" || m.state === "plotting";
    return html`<span class=${connected ? "ok" : "bad"}>${icon(connected ? "plug" : "plugOff")}${name}</span>
      ${connected ? html`<span class=${m.power_ok ? "" : "bad"}>${m.power_ok ? "Power OK" : "Power adapter unplugged"}</span>` : nothing}
      ${connected ? html`<span class=${homeSet ? "" : "bad"}>${homeSet ? "Home set" : "Home not set"}</span>` : nothing}
      <span>Pen ${where(pen)}</span>
      <span>Cursor ${where(this.app.cursor.state.point)}</span>
      ${plotting ? html`<span class="bad">Keep the laptop open while plotting.</span>` : nothing}
      <span class="spacer"></span>
      <select aria-label="Units" .value=${live(units)} @change=${(e: Event) => this.app.setUnits((e.target as HTMLSelectElement).value as Units)}>
        ${UNITS.map((u) => html`<option value=${u} ?selected=${u === units}>${u}</option>`)}
      </select>`;
  }
}

customElements.define("rp-statusbar", RpStatusbar);
