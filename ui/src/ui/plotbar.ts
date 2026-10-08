/** The control bar's right end (spec §2.2): pen times and the total, and the plot buttons. */
import { css, html, nothing } from "lit";
import { disabledReason } from "../state/reasons";
import { formatDuration } from "../state/plotting";
import { StoreController } from "../state/store";
import { AppElement } from "./base";
import { icon, type IconName } from "./icons";
import { controls } from "./styles";

interface PlotButton {
  label: string;
  iconName?: IconName;
  primary?: boolean;
  reason: string | null;
  run: () => void;
}

const WAITING: Record<string, string> = { pausing: "Pausing…", homing: "Sending the pen Home…" };
const AT_REST_OR_DONE = ["idle", "ready", "done"];

function swatch(color: string): string {
  return color === "#000000" ? "var(--ink-black)" : color;
}

export class RpPlotbar extends AppElement {
  static styles = [
    controls,
    css`
      :host {
        display: flex;
        align-items: center;
        gap: 6px;
        white-space: nowrap;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: var(--text-dim);
      }
      .chip i {
        width: 9px;
        height: 9px;
        border-radius: 2px;
      }
      .total {
        margin: 0 6px 0 2px;
        color: var(--text);
      }
      .waiting {
        color: var(--text-dim);
      }
    `,
  ];

  constructor() {
    super();
    new StoreController(this, this.app.progress);
  }

  private buttons(): PlotButton[] {
    const { app, s } = this;
    const state = s.plot.state;
    if (state === "paused" || state === "paused_at_home") {
      return [
        { label: "Resume", iconName: "play", primary: true, reason: null, run: () => void app.plotAction("resume") },
        ...(state === "paused" ? [{ label: "Return Home", iconName: "home" as IconName, reason: null, run: () => void app.plotAction("home") }] : []),
        { label: "Cancel plot", reason: null, run: () => void app.plotAction("cancel") },
      ];
    }
    const waiting = WAITING[state] ?? null;
    return [
      { label: "Start", iconName: "play", primary: true, reason: waiting ?? disabledReason("start", s), run: () => void app.startPlot() },
      { label: "Pause", iconName: "pause", reason: waiting ?? disabledReason("pause", s), run: () => app.pause() },
      { label: "Stop", iconName: "stop", reason: waiting ?? disabledReason("stop", s), run: () => app.stopPlot() },
    ];
  }

  private times() {
    const s = this.s;
    const progress = this.app.progress.state.value;
    if (s.preparing) return html`<span class="total" title="The plot is being prepared.">…</span>`;
    if (!s.summary) {
      const why = s.prepareProblem ?? (s.machine.model === null ? "Times appear once the plotter's model is known." : "Times appear once something is placed.");
      return html`<span class="total" title=${why}>—</span>`;
    }
    const chips = s.summary.layers.map(
      (layer) =>
        html`<span class="chip" title=${`${layer.name} pen`}><i style=${`background: ${swatch(layer.color)}`}></i>${formatDuration(layer.seconds)}</span>`,
    );
    const warnings = s.summary.warnings.join(" ");
    const total =
      progress && !AT_REST_OR_DONE.includes(s.plot.state)
        ? `${formatDuration(progress.seconds_left)} left`
        : `Total ${formatDuration(s.summary.total_seconds)}`;
    return html`${chips}<span class="total" title=${warnings}>${total}</span>${warnings
        ? html`<span class="chip" title=${warnings}>${icon("alert")}</span>`
        : nothing}`;
  }

  render() {
    const waiting = WAITING[this.s.plot.state];
    return html`${this.times()}${waiting ? html`<span class="waiting">${waiting}</span>` : nothing}${this.buttons().map(
      (b) => html`<button
        class=${b.primary ? "primary" : ""}
        aria-disabled=${b.reason ? "true" : "false"}
        title=${b.reason ?? b.label}
        @click=${() => (b.reason ? this.app.explain(b.reason) : b.run())}
      >
        ${b.iconName ? icon(b.iconName) : nothing}${b.label}
      </button>`,
    )}`;
  }
}

customElements.define("rp-plotbar", RpPlotbar);
