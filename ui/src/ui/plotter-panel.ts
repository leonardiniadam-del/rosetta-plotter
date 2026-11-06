/** The Plotter panel (spec §2.5): the model, the pen, its live height, a test mark, and the jog pad. */
import { css, html } from "lit";
import { live } from "lit/directives/live.js";
import { disabledReason } from "../state/reasons";
import { AppElement } from "./base";
import { icon, type IconName } from "./icons";
import { controls } from "./styles";

export class RpPlotterPanel extends AppElement {
  static styles = [
    controls,
    css`
      :host {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .line {
        display: flex;
        align-items: center;
        gap: 6px;
        color: var(--text-dim);
      }
      .name {
        flex: 1;
        color: var(--text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      input[type="range"] {
        flex: 1;
      }
      .value {
        min-width: 22px;
        text-align: right;
        color: var(--text);
      }
      .pad {
        display: grid;
        grid-template-columns: repeat(3, 32px);
        gap: 3px;
        justify-content: center;
      }
      .pad button {
        width: 32px;
        padding: 0;
        justify-content: center;
      }
      .pad .step {
        font-size: var(--font-size-small);
      }
    `,
  ];

  private button(label: string, iconName: IconName, reason: string | null, run: () => void) {
    return html`<button
      aria-label=${label}
      title=${reason ? `${label}: ${reason}` : label}
      aria-disabled=${reason ? "true" : "false"}
      @click=${() => (reason ? this.app.explain(reason) : run())}
    >
      ${icon(iconName)}
    </button>`;
  }

  private releaseHold = (): void => this.app.jogRelease();

  connectedCallback(): void {
    super.connectedCallback();
    window.addEventListener("blur", this.releaseHold);
  }

  disconnectedCallback(): void {
    window.removeEventListener("blur", this.releaseHold);
    this.app.jogRelease();
    super.disconnectedCallback();
  }

  /** A jog arrow: press and hold to keep moving (spec §3); Enter or Space moves one step. */
  private arrow(label: string, iconName: IconName, reason: string | null, dx: number, dy: number) {
    const down = (event: PointerEvent) => {
      if (event.button !== 0) return;
      if (reason) {
        this.app.explain(reason);
        return;
      }
      try {
        (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
      } catch {
        // Not every pointer can be captured; pointerup still ends the hold.
      }
      this.app.jogHold(dx, dy);
    };
    return html`<button
      aria-label=${label}
      title=${reason ? `${label}: ${reason}` : `${label}. Hold to keep moving`}
      aria-disabled=${reason ? "true" : "false"}
      @pointerdown=${down}
      @pointerup=${this.releaseHold}
      @pointercancel=${this.releaseHold}
      @lostpointercapture=${this.releaseHold}
      @click=${(event: MouseEvent) => {
        // A pointer press already moved; detail 0 is Enter or Space on the focused button.
        if (event.detail !== 0) return;
        if (reason) this.app.explain(reason);
        else void this.app.jog(dx, dy);
      }}
    >
      ${icon(iconName)}
    </button>`;
  }

  render() {
    const s = this.s;
    const m = s.machine;
    const move = disabledReason("move", s);
    const model = disabledReason("model", s);
    const name =
      m.state === "no_plotter" ? "No plotter" : m.state === "needs_model" ? "Model unknown" : [m.label, m.model_name].filter(Boolean).join(" · ");
    return html`<div class="line">
        <span class="name">${name}</span>
        <button
          aria-disabled=${model ? "true" : "false"}
          title=${model ?? "Choose which AxiDraw this is"}
          @click=${() => this.app.openModelDialog()}
        >Plotter model…</button>
      </div>
      <label class="line"
        >Pen
        <select aria-label="Pen type" .value=${live(m.pen_type)} @change=${(e: Event) => this.app.setPen(m.pen_down, (e.target as HTMLSelectElement).value)}>
          ${(s.start?.pen_types ?? []).map((t) => html`<option value=${t.key} ?selected=${t.key === m.pen_type}>${t.label}</option>`)}
        </select></label
      >
      <label class="line"
        >Height
        <input
          type="range"
          min="0"
          max=${s.start?.pen_down_max ?? 80}
          step="1"
          .value=${String(m.pen_down)}
          aria-label="Pen-down height"
          @input=${(e: Event) => this.app.setPen(Number((e.target as HTMLInputElement).value), m.pen_type)}
        /><span class="value">${m.pen_down}</span></label
      >
      <div class="line">
        ${this.button("Raise pen", "penUp", move, () => void this.app.pen(false))}
        ${this.button("Lower pen", "penDown", move, () => void this.app.pen(true))}
        <button
          aria-disabled=${move ? "true" : "false"}
          title=${move ?? "Draw a 10 mm line by the paper's corner nearest HOME, then go Home"}
          @click=${() => (move ? this.app.explain(move) : void this.app.testMark())}
        >Test mark</button>
      </div>
      <div class="pad" role="group" aria-label="Move the pen (pen up)">
        <span></span>${this.arrow("Move pen up (on screen)", "arrowUp", move, 0, -1)}<span></span>
        ${this.arrow("Move pen left (on screen)", "arrowLeft", move, -1, 0)}
        <button class="step" aria-label=${`Step ${s.jogStep} mm (click to change)`} @click=${() => this.app.setJogStep(s.jogStep === 1 ? 10 : 1)}>
          ${s.jogStep} mm
        </button>
        ${this.arrow("Move pen right (on screen)", "arrowRight", move, 1, 0)}
        <span></span>${this.arrow("Move pen down (on screen)", "arrowDown", move, 0, 1)}<span></span>
      </div>`;
  }
}

customElements.define("rp-plotter", RpPlotterPanel);
