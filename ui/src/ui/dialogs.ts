/** The few dialogs: page picker, plotter model, text (diagnostics), shortcuts and About. Esc cancels. */
import { css, html, nothing } from "lit";
import { SHORTCUT_HELP } from "../app/shortcut-help";
import { formatLength } from "../geometry/units";
import type { Dialog } from "../state/store";
import { AppElement } from "./base";
import { controls } from "./styles";

const MODEL_FIRST = "Choose the model on the plotter's label first.";

export class RpDialogs extends AppElement {
  static properties = { chosen: { state: true }, hint: { state: true } };

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
  private lastDialog: unknown = null;

  constructor() {
    super();
    this.chosen = null;
    this.hint = "";
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
  }

  protected updated(): void {
    const dialog = this.current();
    if (dialog === this.lastDialog) return;
    this.lastDialog = dialog;
    if (!dialog) return;
    const first =
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
