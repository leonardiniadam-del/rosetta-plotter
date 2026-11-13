/** The Plotter panel (spec §2.5): the model, the pen, its live height, a test mark, and the jog pad. */
import { css, html, nothing } from "lit";
import { live } from "lit/directives/live.js";
import { JOG_STEPS } from "../app/app";
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
      .steps {
        display: flex;
        gap: 3px;
        justify-content: center;
      }
      .steps button {
        flex: 1;
        min-width: 0;
        padding: 0 2px;
        justify-content: center;
        font-size: var(--font-size-small);
      }
      .offset .value {
        min-width: 0;
        font-variant-numeric: tabular-nums;
      }
      .wide {
        flex: 1;
        justify-content: center;
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

  /** A button with its name written on it. */
  private labelled(label: string, iconName: IconName, reason: string | null, tip: string, run: () => void) {
    return html`<button
      class="wide"
      title=${reason ?? tip}
      aria-disabled=${reason ? "true" : "false"}
      @click=${() => (reason ? this.app.explain(reason) : run())}
    >
      ${icon(iconName)}${label}
    </button>`;
  }

  /** At a pen change: how far the arrows have nudged the new pen, which is how far over it will plot. */
  private offset() {
    const align = this.s.plot.align;
    if (!align?.available) return nothing;
    const signed = (mm: number) => `${mm > 0 ? "+" : mm < 0 ? "\u2212" : ""}${Math.abs(mm).toFixed(2)}`;
    const [x, y] = align.offset;
    return html`<div class="line offset" role="status"
      title="Nudge the new pen onto a line the last pen drew. This pen is then plotted this far over. The Move pen tool and Home don't count."
    >This pen plots <span class="value">X ${signed(x)}, Y ${signed(y)} mm</span> over</div>`;
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
      @pointermove=${(event: PointerEvent) => {
        // The button holds the pointer, so pointerleave never comes: check where the pointer is instead.
        const box = (event.currentTarget as Element).getBoundingClientRect();
        const off = event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom;
        if (off) this.app.jogRelease();
      }}
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
    const pen = disabledReason("pen", s);
    const release = disabledReason("setHome", s);
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
        ${this.labelled("Pen up", "penUp", pen, "Raise the pen where it is", () => void this.app.pen(false))}
        ${this.labelled("Pen down", "penDown", pen, "Lower the pen where it is, to see where the nib lands", () => void this.app.pen(true))}
      </div>
      <div class="line">
        ${this.labelled("Release motors", "release", release, "Let go of the motors so the pen slides by hand. Use Set Home afterwards", () => void this.app.releaseMotors())}
        <button
          aria-disabled=${move ? "true" : "false"}
          title=${move ?? "Draw a 10 mm line by the paper's corner nearest HOME, then go Home"}
          @click=${() => (move ? this.app.explain(move) : void this.app.testMark())}
        >Test mark</button>
      </div>
      <div class="pad" role="group" aria-label="Move the pen (pen up)">
        <span></span>${this.arrow("Move pen up (on screen)", "arrowUp", move, 0, -1)}<span></span>
        ${this.arrow("Move pen left (on screen)", "arrowLeft", move, -1, 0)}
        ${this.button("Send the pen Home", "home", move, () => void this.app.movePenHome())}
        ${this.arrow("Move pen right (on screen)", "arrowRight", move, 1, 0)}
        <span></span>${this.arrow("Move pen down (on screen)", "arrowDown", move, 0, 1)}<span></span>
      </div>
      ${this.offset()}
      <div class="steps" role="group" aria-label="Step for each press, in mm">
        ${JOG_STEPS.map(
          (step) => html`<button
            aria-pressed=${String(s.jogStep === step)}
            aria-label=${`Step ${step} mm`}
            title=${`Each press of an arrow moves the pen ${step} mm`}
            @click=${() => this.app.setJogStep(step)}
          >${step}</button>`,
        )}
      </div>`;
  }
}

customElements.define("rp-plotter", RpPlotterPanel);
