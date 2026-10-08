/** The control bar (spec §2.2): the selected drawing's numbers, or the paper's settings. */
import { css, html, nothing } from "lit";
import { live } from "lit/directives/live.js";
import { ONE_DRAWING, STRETCH_TURNED } from "../app/app";
import { isQuarterTurn } from "../geometry/placement";
import { overallFraction } from "../state/plotting";
import { disabledReason } from "../state/reasons";
import { jobOf, plotRunning, selectedPieces, selectionBox } from "../state/selectors";
import { StoreController } from "../state/store";
import { AppElement } from "./base";
import "./field";
import { icon } from "./icons";
import "./plotbar";
import { controls } from "./styles";

type Commit = CustomEvent<number>;

export class RpControlbar extends AppElement {
  static styles = [
    controls,
    css`
      :host {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 0 10px;
        overflow: hidden;
        position: relative;
      }
      .left {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 8px;
        overflow-x: auto;
        overflow-y: hidden;
        scrollbar-width: thin;
        white-space: nowrap;
      }
      .progress {
        position: absolute;
        left: 0;
        bottom: 0;
        height: 2px;
        background: var(--accent);
      }
      .name {
        flex: none; /* .left scrolls instead of squeezing the name away */
        max-width: 140px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--text-dim);
      }
      .sep {
        width: 1px;
        align-self: stretch;
        margin: 6px 0;
        background: var(--line);
      }
      label {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: var(--text-dim);
      }
      label select {
        color: var(--text);
      }
    `,
  ];

  constructor() {
    super();
    new StoreController(this, this.app.progress);
  }

  render() {
    const s = this.s;
    const left = s.selection.length > 0 ? this.drawingControls() : this.paperControls();
    const fraction = plotRunning(s) && s.summary ? overallFraction(s.summary.total_seconds, this.app.progress.state.value) : 0;
    return html`<div class="left">${left}</div><rp-plotbar></rp-plotbar>${fraction > 0
        ? html`<div class="progress" style=${`width: ${(fraction * 100).toFixed(1)}%`}></div>`
        : nothing}`;
  }

  private drawingControls() {
    const s = this.s;
    const units = s.units;
    const box = selectionBox(s);
    if (!box) return nothing;
    const pieces = selectedPieces(s);
    const one = pieces.length === 1 ? pieces[0] : null;
    const job = one ? jobOf(s, one) : undefined;
    const p = one?.placement;
    const locked = disabledReason("arrange", s);
    const onlyOne = one ? null : ONE_DRAWING;
    const turned = p ? !isQuarterTurn(p.rotation) : false;
    const sizeReason = onlyOne ?? locked ?? (!s.linkScale && turned ? STRETCH_TURNED : null);
    const twoScales = p ? !s.linkScale || Math.abs(p.scale - p.scale_y) > 1e-9 : false;
    return html`<span class="name" title=${job?.name ?? ""}>${job ? job.name : `${pieces.length} drawings`}</span>
      <rp-field label="X" .value=${box.x} .units=${units} ?disabled=${!!locked} tip=${locked ?? "Left edge, from the paper's corner"}
        @commit=${(e: Commit) => this.app.moveSelectionTo(e.detail, null)}></rp-field>
      <rp-field label="Y" .value=${box.y} .units=${units} ?disabled=${!!locked} tip=${locked ?? "Top edge, from the paper's corner"}
        @commit=${(e: Commit) => this.app.moveSelectionTo(null, e.detail)}></rp-field>
      <span class="sep"></span>
      <rp-field label="W" .value=${box.width} .units=${units} ?disabled=${!!sizeReason} tip=${sizeReason ?? "Width"}
        @commit=${(e: Commit) => this.app.resizeSelected({ width: e.detail })}></rp-field>
      <button
        class="icon"
        aria-label=${s.linkScale ? "Proportions linked (click to unlink)" : "Proportions unlinked (click to link)"}
        aria-pressed=${String(s.linkScale)}
        @click=${() => this.app.toggleLink()}
      >
        ${icon(s.linkScale ? "link" : "unlink")}
      </button>
      <rp-field label="H" .value=${box.height} .units=${units} ?disabled=${!!sizeReason} tip=${sizeReason ?? "Height"}
        @commit=${(e: Commit) => this.app.resizeSelected({ height: e.detail })}></rp-field>
      <span class="sep"></span>
      ${p
        ? twoScales
          ? html`<rp-field kind="percent" label="W%" .value=${p.scale} ?disabled=${!!locked} tip=${locked ?? "Scale along the drawing's width"}
                @commit=${(e: Commit) =>
                  s.linkScale ? this.app.setScale(e.detail, p.scale_y * (e.detail / p.scale)) : this.app.setScale(e.detail, p.scale_y)}></rp-field>
              <rp-field kind="percent" label="H%" .value=${p.scale_y} ?disabled=${!!locked} tip=${locked ?? "Scale along the drawing's height"}
                @commit=${(e: Commit) =>
                  s.linkScale ? this.app.setScale(p.scale * (e.detail / p.scale_y), e.detail) : this.app.setScale(p.scale, e.detail)}></rp-field>`
          : html`<rp-field kind="percent" label="Scale" .value=${p.scale} ?disabled=${!!locked} tip=${locked ?? "Scale, keeping proportions"}
              @commit=${(e: Commit) => this.app.setScale(e.detail, e.detail)}></rp-field>`
        : nothing}
      <rp-field kind="angle" label="Angle" .value=${p?.rotation ?? 0} ?disabled=${!!(onlyOne ?? locked)}
        tip=${onlyOne ?? locked ?? "Turn clockwise, in degrees"} @commit=${(e: Commit) => this.app.rotateSelectedTo(e.detail)}></rp-field>`;
  }

  private paperControls() {
    const s = this.s;
    const units = s.units;
    const m = s.material;
    const custom = s.paper.size === "custom";
    const portrait = s.paper.orientation === "portrait";
    const mark = disabledReason("markCorner", s);
    const locked = disabledReason("paper", s);
    return html`<label
        >Paper
        <select aria-label="Paper size" ?disabled=${!!locked} title=${locked ?? ""} .value=${live(s.paper.size)} @change=${(e: Event) => this.choosePaper((e.target as HTMLSelectElement).value)}>
          ${(s.start?.papers ?? []).map((p) => html`<option value=${p.key} ?selected=${p.key === s.paper.size}>${p.label}</option>`)}
          <option value="custom" ?selected=${custom}>Custom</option>
        </select></label
      >
      <button aria-pressed=${String(!portrait)} ?disabled=${!!locked} title=${locked ?? ""} @click=${() => this.app.setOrientation("landscape")}>Landscape</button>
      <button aria-pressed=${String(portrait)} ?disabled=${!!locked} title=${locked ?? ""} @click=${() => this.app.setOrientation("portrait")}>Portrait</button>
      <rp-field label="W" .value=${m.width} .units=${units} ?readonly=${!custom} ?disabled=${!!locked}
        tip=${locked ?? (custom ? "Paper width" : "Choose Custom to type a size")}
        @commit=${(e: Commit) => this.app.setPaper("custom", s.paper.orientation, e.detail, m.height)}></rp-field>
      <rp-field label="H" .value=${m.height} .units=${units} ?readonly=${!custom} ?disabled=${!!locked}
        tip=${locked ?? (custom ? "Paper height" : "Choose Custom to type a size")}
        @commit=${(e: Commit) => this.app.setPaper("custom", s.paper.orientation, m.width, e.detail)}></rp-field>
      <span class="sep"></span>
      <rp-field label="X" .value=${m.x} .units=${units} ?disabled=${!!locked} tip=${locked ?? "The paper's corner nearest HOME, measured from Home"}
        @commit=${(e: Commit) => this.app.movePaper(e.detail, m.y)}></rp-field>
      <rp-field label="Y" .value=${m.y} .units=${units} ?disabled=${!!locked} tip=${locked ?? "The paper's corner nearest HOME, measured from Home"}
        @commit=${(e: Commit) => this.app.movePaper(m.x, e.detail)}></rp-field>
      <button
        aria-disabled=${mark ? "true" : "false"}
        title=${mark ?? "Set the paper's corner nearest HOME to where the pen is"}
        @click=${() => (mark ? this.app.explain(mark) : void this.app.markCorner())}
      >
        ${icon("mark")}Mark corner at pen
      </button>
      <span class="sep"></span>
      <rp-field label="Margin" .value=${s.margin} .units=${units} ?disabled=${!!locked}
        tip=${locked ?? "Guides only; also where double-click places a drawing"}
        @commit=${(e: Commit) => this.app.setMargin(e.detail)}></rp-field>`;
  }

  private choosePaper(size: string): void {
    const s = this.s;
    if (size === "custom") void this.app.setPaper("custom", s.paper.orientation, s.material.width, s.material.height);
    else void this.app.setPaper(size, s.paper.orientation);
  }
}

customElements.define("rp-controlbar", RpControlbar);
