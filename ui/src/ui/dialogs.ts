/** The few dialogs: page picker, plotter model, text (diagnostics), shortcuts and About. Esc cancels. */
import { css, html, nothing } from "lit";
import { live } from "lit/directives/live.js";
import { SHORTCUT_HELP } from "../app/shortcut-help";
import type { AdvancedValues } from "../bridge/contract";
import { formatLength, UNITS, UNIT_NAMES, type Units } from "../geometry/units";
import { AUTOMATIC, CHOICE_LABELS, MANUAL_START, changedAdvanced, checkAdvanced } from "../state/advanced";
import type { Dialog } from "../state/store";
import { AppElement } from "./base";
import "./field";
import { controls } from "./styles";

const MODEL_FIRST = "Choose the model on the plotter's label first.";

export class RpDialogs extends AppElement {
  static properties = {
    chosen: { state: true },
    hint: { state: true },
    tab: { state: true },
    draft: { state: true },
    problem: { state: true },
    saving: { state: true },
  };

  static styles = [
    controls,
    css`
      .backdrop {
        position: fixed;
        inset: 0;
        z-index: 50;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.45);
      }
      .dialog {
        display: flex;
        flex-direction: column;
        gap: 12px;
        min-width: 320px;
        max-width: 560px;
        padding: 16px;
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 4px;
        box-shadow: var(--menu-shadow);
      }
      h2 {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
      }
      p {
        margin: 0;
      }
      .buttons {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
      }
      .models {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .model {
        display: grid;
        grid-template-columns: auto 1fr auto;
        gap: 8px;
        align-items: center;
      }
      textarea {
        width: 100%;
        box-sizing: border-box;
        font: 11px/1.4 Consolas, monospace;
        color: var(--text);
        background: var(--panel-raised);
        border: 1px solid var(--line);
        user-select: text;
      }
      td {
        padding: 2px 12px 2px 0;
      }
      .keys {
        color: var(--text-dim);
      }
      .hint {
        color: var(--warning);
      }
      .tabs {
        display: flex;
        gap: 4px;
        border-bottom: 1px solid var(--line);
      }
      .tabs [role="tab"] {
        border: none;
        background: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
      }
      .tabs [aria-selected="true"] {
        border-bottom-color: var(--accent);
      }
      .form {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 6px 12px;
        align-items: center;
      }
      .inline {
        display: inline-flex;
        gap: 8px;
        align-items: center;
      }
      .grow {
        flex: 1;
      }
      .pen {
        display: flex;
        gap: 12px;
        align-items: center;
      }
      .pen i {
        flex: none;
        width: 28px;
        height: 28px;
        border-radius: 4px;
        border: 1px solid var(--line);
      }
    `,
  ];

  declare chosen: number | null;
  declare hint: string;
  declare tab: "general" | "advanced";
  declare draft: AdvancedValues;
  declare problem: string;
  declare saving: boolean;
  private lastDialog: unknown = null;
  /** The Settings dialog whose draft is showing; a pen change in between doesn't make it a new one. */
  private lastSettings: unknown = null;

  constructor() {
    super();
    this.chosen = null;
    this.hint = "";
    this.tab = "general";
    this.draft = {};
    this.problem = "";
    this.saving = false;
  }

  connectedCallback(): void {
    super.connectedCallback();
    window.addEventListener("keydown", this.onKey, true);
  }

  disconnectedCallback(): void {
    window.removeEventListener("keydown", this.onKey, true);
    super.disconnectedCallback();
  }

  protected willUpdate(): void {
    const dialog = this.s.dialog;
    if (dialog !== this.lastDialog && dialog?.kind === "model") {
      this.chosen = this.s.machine.model;
      this.hint = "";
    }
    if (dialog?.kind !== "settings") this.lastSettings = null;
    else if (dialog !== this.lastSettings) {
      this.lastSettings = dialog;
      this.tab = "general";
      this.draft = { ...this.s.advanced };
      this.problem = "";
      this.saving = false;
    }
  }

  protected updated(): void {
    const dialog = this.current();
    if (dialog === this.lastDialog) return;
    this.lastDialog = dialog;
    if (!dialog) return;
    // The pen change opens on Continue: a student who swaps the pen and presses Enter or Space must not cancel the plot.
    const first =
      (dialog === "pen" ? this.renderRoot.querySelector<HTMLElement>(".dialog button.primary") : null) ??
      this.renderRoot.querySelector<HTMLElement>(".dialog input:checked") ??
      this.renderRoot.querySelector<HTMLElement>(".dialog input, .dialog select, .dialog textarea, .dialog button");
    first?.focus();
  }

  /** What the window is asking right now: the pen change comes ahead of any other dialog. */
  private current(): unknown {
    return this.s.plot.state === "load_pen" ? "pen" : this.s.dialog;
  }

  private onKey = (event: KeyboardEvent): void => {
    if (!this.current()) return;
    // A number box (the margin) commits on Enter and reverts on Esc itself; the dialog acts on the next press.
    if (["Enter", "Escape"].includes(event.key) && event.composedPath().some((el) => el instanceof HTMLElement && el.tagName === "RP-FIELD")) return;
    if (event.key === "Escape") {
      event.stopPropagation();
      if (this.s.plot.state !== "load_pen") this.cancel(); // Esc never cancels a plot
      return;
    }
    const target = event.composedPath()[0];
    const inButtonOrText = target instanceof HTMLElement && ["BUTTON", "TEXTAREA"].includes(target.tagName);
    if (event.key === "Enter" && !inButtonOrText) {
      event.preventDefault();
      event.stopPropagation();
      this.renderRoot.querySelector<HTMLButtonElement>(".dialog button.primary")?.click();
    }
  };

  private cancel(): void {
    const dialog = this.s.dialog;
    if (dialog?.kind === "pages") dialog.resolve(null);
    else this.app.closeDialog();
  }

  render() {
    if (this.s.plot.state === "load_pen") return this.frame(this.penChange());
    const dialog = this.s.dialog;
    if (!dialog) return nothing;
    return this.frame(this.body(dialog), () => this.cancel());
  }

  private frame(body: unknown, onBackdrop?: () => void) {
    return html`<div class="backdrop" @click=${(e: Event) => e.target === e.currentTarget && onBackdrop?.()}>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="title">${body}</div>
    </div>`;
  }

  private penChange() {
    const plot = this.s.plot;
    const color = plot.color === "#000000" ? "var(--ink-black)" : (plot.color ?? "transparent");
    return html`<h2 id="title">Change the pen</h2>
      <div class="pen"><i style=${`background: ${color}`}></i><p class="message">${plot.message}</p></div>
      <div class="buttons">
        <button @click=${() => void this.app.plotAction("cancel")}>Cancel plot</button>
        <button class="primary" @click=${() => void this.app.plotAction("continue")}>Continue</button>
      </div>`;
  }

  private close() {
    return html`<div class="buttons"><button class="primary" @click=${() => this.app.closeDialog()}>Close</button></div>`;
  }

  private body(dialog: Dialog) {
    switch (dialog.kind) {
      case "pages":
        return html`<h2 id="title">Which page of ${dialog.name}?</h2>
          <label>Page <select id="page">${Array.from({ length: dialog.pages }, (_, i) => html`<option value=${i}>${i + 1}</option>`)}</select></label>
          <div class="buttons">
            <button @click=${() => dialog.resolve(null)}>Cancel</button>
            <button class="primary" @click=${() => dialog.resolve(Number((this.renderRoot.querySelector("#page") as HTMLSelectElement).value))}>
              Import page
            </button>
          </div>`;
      case "model":
        return this.modelForm();
      case "text":
        return html`<h2 id="title">${dialog.title}</h2>
          <textarea readonly rows="14" .value=${dialog.text} @focus=${(e: FocusEvent) => (e.target as HTMLTextAreaElement).select()}></textarea>
          <p class="dim">Select it all and press Ctrl+C to copy.</p>
          ${this.close()}`;
      case "shortcuts":
        return html`<h2 id="title">Keyboard shortcuts</h2>
          <table>${SHORTCUT_HELP.map(([action, keys]) => html`<tr><td>${action}</td><td class="keys">${keys}</td></tr>`)}</table>
          ${this.close()}`;
      case "confirm":
        return html`<h2 id="title">${dialog.title}</h2>
          ${dialog.message ? html`<p class="message">${dialog.message}</p>` : nothing}
          <div class="buttons">
            <button @click=${() => this.app.closeDialog()}>${dialog.cancel}</button>
            <button class="primary" @click=${() => dialog.run()}>${dialog.confirm}</button>
          </div>`;
      case "settings":
        return this.settings();
      case "about":
        return html`<h2 id="title">Rosetta Plotter</h2>
          <p>Version ${this.s.start?.version ?? ""}</p>
          <p class="dim">
            Pen plotting for AxiDraw machines. Free software under the GNU AGPL 3.0. Includes the AxiDraw software by
            Evil Mad Scientist Laboratories (GPL).
          </p>
          ${this.close()}`;
    }
  }

  private settings() {
    const s = this.s;
    const tabs = html`<div class="tabs" role="tablist">
      ${(["general", "advanced"] as const).map(
        (name) => html`<button role="tab" aria-selected=${String(this.tab === name)} @click=${() => (this.tab = name)}>
          ${name === "general" ? "General" : "Advanced"}
        </button>`,
      )}
    </div>`;
    if (this.tab === "general") {
      return html`<h2 id="title">Settings</h2>
        ${tabs}
        <div class="form">
          <label for="units">Units</label>
          <select id="units" .value=${live(s.units)} @change=${(e: Event) => void this.app.setUnits((e.target as HTMLSelectElement).value as Units)}>
            ${UNITS.map((u) => html`<option value=${u} ?selected=${u === s.units}>${UNIT_NAMES[u]}</option>`)}
          </select>
          <label>Margin</label>
          <rp-field
            label=""
            .value=${s.margin}
            .units=${s.units}
            tip="Margin"
            @commit=${(e: CustomEvent<number>) => void this.app.setMargin(e.detail)}
          ></rp-field>
          <label for="grid">Show grid</label>
          <input id="grid" type="checkbox" .checked=${s.view.grid} @change=${() => this.app.toggleView("grid")} />
          <label for="skip-white">Skip white shapes</label>
          <input
            id="skip-white"
            type="checkbox"
            .checked=${s.skipWhite}
            @change=${(e: Event) => void this.app.setSkipWhite((e.target as HTMLInputElement).checked)}
          />
        </div>
        <div class="buttons"><button class="primary" @click=${() => this.app.closeDialog()}>Close</button></div>`;
    }
    const options = s.start?.advanced_options;
    const names = options ? Object.keys(options.labels) : [];
    return html`<h2 id="title">Settings</h2>
      ${tabs}
      <p class="dim">These change how the plotter moves. Most students never need them.</p>
      <div class="form">${names.map((name) => this.advancedRow(name))}</div>
      ${this.problem ? html`<p class="hint" role="alert">${this.problem}</p>` : nothing}
      <div class="buttons">
        <button @click=${() => options && ((this.draft = { ...options.defaults }), (this.problem = ""))}>Restore defaults</button>
        <span class="grow"></span>
        <button @click=${() => this.app.closeDialog()}>Cancel</button>
        <button class="primary" aria-disabled=${this.saving ? "true" : "false"} @click=${() => void this.saveAdvanced()}>Save</button>
      </div>`;
  }

  private advancedRow(name: string) {
    const options = this.s.start?.advanced_options;
    if (!options) return nothing;
    const label = options.labels[name];
    const value = this.draft[name];
    const id = `adv-${name}`;
    const set = (next: number | boolean | null) => {
      this.draft = { ...this.draft, [name]: next };
      this.problem = "";
    };
    if (name === "hiding") {
      return html`<label for=${id}>${label}</label>
        <input id=${id} type="checkbox" .checked=${value === true} @change=${(e: Event) => set((e.target as HTMLInputElement).checked)} />`;
    }
    const choices = options.choices[name];
    if (choices) {
      return html`<label for=${id}>${label}</label>
        <select id=${id} .value=${live(String(value))} @change=${(e: Event) => set(Number((e.target as HTMLSelectElement).value))}>
          ${choices.map((c) => html`<option value=${c} ?selected=${c === value}>${CHOICE_LABELS[name]?.[c] ?? c}</option>`)}
        </select>`;
    }
    const [low, high] = options.ranges[name] ?? [0, 100];
    // "input" as well as "change": Enter saves before the browser sends "change", so the draft must already hold the typing.
    const typed = (e: Event) => {
      const text = (e.target as HTMLInputElement).value.trim();
      set(text === "" ? Number.NaN : Number(text));
    };
    return html`<label for=${id}>${label}</label>
      <span class="inline">
        <input
          id=${id}
          type="number"
          min=${low}
          max=${high}
          step="1"
          ?disabled=${value === null}
          .value=${live(typeof value === "number" && !Number.isNaN(value) ? String(value) : "")}
          @input=${typed}
          @change=${typed}
        />
        ${AUTOMATIC.includes(name)
          ? html`<label
              ><input
                type="checkbox"
                .checked=${value === null}
                @change=${(e: Event) => set((e.target as HTMLInputElement).checked ? null : (MANUAL_START[name] ?? low))}
              />Automatic</label
            >`
          : nothing}
      </span>`;
  }

  private async saveAdvanced(): Promise<void> {
    const options = this.s.start?.advanced_options;
    if (!options || this.saving) return;
    const problem = checkAdvanced(this.draft, options);
    if (problem) {
      this.problem = problem;
      return;
    }
    this.saving = true;
    const refused = await this.app.setAdvanced(changedAdvanced(this.draft, this.s.advanced));
    this.saving = false;
    if (refused) this.problem = refused;
    else this.app.closeDialog();
  }

  private modelForm() {
    const models = this.s.start?.models ?? [];
    const { units, machine } = this.s;
    return html`<h2 id="title">Which AxiDraw is this?</h2>
      <p class="dim">It's on the label on the machine. It's saved on the plotter, so other laptops will know it too.</p>
      <div class="models" role="radiogroup" aria-label="Model">
        ${models.map(
          (m) =>
            html`<label class="model"
              ><input type="radio" name="model" value=${m.number} ?checked=${m.number === this.chosen} @change=${() => {
                this.chosen = m.number;
                this.hint = "";
              }} /><span>${m.name}</span
              ><span class="dim">${formatLength(m.travel[0], units)} × ${formatLength(m.travel[1], units, true)}</span></label
            >`,
        )}
      </div>
      <label
        >Pen lift
        <select id="penlift">
          <option value="1">Standard</option>
          <option value="3" ?selected=${machine.penlift === 3}>Brushless upgrade</option>
        </select></label
      >
      <label>Name <input id="label" maxlength="40" .value=${machine.label ?? ""} placeholder="PSU Lab" /></label>
      ${this.hint ? html`<p class="hint" role="alert">${this.hint}</p>` : nothing}
      <div class="buttons">
        <button @click=${() => this.app.closeDialog()}>Cancel</button>
        <button
          class="primary"
          aria-disabled=${this.chosen === null ? "true" : "false"}
          title=${this.chosen === null ? MODEL_FIRST : ""}
          @click=${() => (this.chosen === null ? (this.hint = MODEL_FIRST) : this.saveModel())}
        >
          Save
        </button>
      </div>`;
  }

  private saveModel(): void {
    const root = this.renderRoot;
    const model = this.chosen;
    if (model === null) return;
    const penlift = Number((root.querySelector("#penlift") as HTMLSelectElement).value);
    const label = (root.querySelector("#label") as HTMLInputElement).value.trim();
    void this.app.identify(model, penlift, label);
  }
}

customElements.define("rp-dialogs", RpDialogs);
