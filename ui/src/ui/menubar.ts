/** The menu bar (spec §2.1). A greyed-out item says why in its tooltip, and in the strip when clicked. */
import { css, html, nothing } from "lit";
import { UNIT_NAMES, UNITS } from "../geometry/units";
import { disabledReason } from "../state/reasons";
import { AppElement } from "./base";
import { icon } from "./icons";
import { controls } from "./styles";

interface Item {
  label: string;
  shortcut?: string;
  reason?: string | null;
  checked?: boolean;
  radio?: boolean;
  run: () => void;
}
type Entry = Item | "separator" | { heading: string };
interface Menu {
  name: string;
  items: Entry[];
}

export class RpMenubar extends AppElement {
  static properties = { open: { state: true } };

  static styles = [
    controls,
    css`
      :host {
        display: flex;
        align-items: stretch;
        padding: 0 6px;
      }
      .brand {
        display: flex;
        align-items: center;
        padding: 0 12px 0 4px;
        font-weight: 600;
      }
      .top {
        position: relative;
        display: flex;
      }
      .title {
        height: 100%;
        background: none;
        border: none;
        border-radius: 0;
      }
      .title[aria-expanded="true"] {
        background: var(--panel-raised);
      }
      .menu {
        position: absolute;
        top: 100%;
        left: 0;
        z-index: 60;
        display: flex;
        flex-direction: column;
        min-width: 260px;
        padding: 4px 0;
        background: var(--panel);
        border: 1px solid var(--line);
        box-shadow: var(--menu-shadow);
      }
      .menu button {
        display: grid;
        grid-template-columns: 18px 1fr auto;
        gap: 8px;
        height: 24px;
        padding: 0 12px 0 6px;
        text-align: left;
        background: none;
        border: none;
        border-radius: 0;
      }
      .menu button:hover:not([aria-disabled="true"]) {
        background: var(--accent);
        color: #fff;
      }
      .keys {
        color: var(--text-dim);
      }
      hr {
        width: 100%;
        margin: 4px 0;
        border: none;
        border-top: 1px solid var(--line);
      }
      .heading {
        padding: 2px 12px 2px 30px;
        color: var(--text-faint);
        font-size: var(--font-size-small);
      }
    `,
  ];

  declare open: string | null;

  constructor() {
    super();
    this.open = null;
  }

  connectedCallback(): void {
    super.connectedCallback();
    window.addEventListener("pointerdown", this.onOutside);
    window.addEventListener("keydown", this.onKey, true);
  }

  disconnectedCallback(): void {
    window.removeEventListener("pointerdown", this.onOutside);
    window.removeEventListener("keydown", this.onKey, true);
    super.disconnectedCallback();
  }

  private onOutside = (event: Event): void => {
    if (this.open && !event.composedPath().includes(this)) this.open = null;
  };

  private onKey = (event: KeyboardEvent): void => {
    if (event.key === "Escape" && this.open) {
      this.open = null;
      event.stopPropagation(); // the page's own Esc (deselect) doesn't run as well
    }
  };

  private menus(): Menu[] {
    const { app, s } = this;
    const arrange = disabledReason("arrange", s);
    const jobId = app.selectedJobId();
    return [
      {
        name: "File",
        items: [
          { label: "Import…", shortcut: "Ctrl+I", run: () => void app.importFiles() },
          { label: "Settings…", shortcut: "Ctrl+,", run: () => app.openSettings() },
          "separator",
          { label: "Copy diagnostics", run: () => void app.copyDiagnostics() },
          "separator",
          { label: "Exit", run: () => void app.exit() },
        ],
      },
      {
        name: "Edit",
        items: [
          { label: "Delete", shortcut: "Del", reason: arrange, run: () => void app.deleteSelection() },
          { label: "Select all", shortcut: "Ctrl+A", reason: s.pieces.length ? null : "Nothing placed on the paper.", run: () => app.selectAll() },
          { label: "Deselect", shortcut: "Ctrl+Shift+A", run: () => app.deselect() },
        ],
      },
      {
        name: "Object",
        items: [
          { label: "Duplicate", shortcut: "Ctrl+D", reason: arrange, run: () => void app.duplicateSelection() },
          { label: "Rotate 90° clockwise", shortcut: "Ctrl+R", reason: arrange, run: () => void app.rotateSelectionBy(90) },
          { label: "Rotate paper 90°", shortcut: "Ctrl+Shift+R", reason: disabledReason("rotatePaper", s), run: () => void app.rotatePaper() },
          { label: "Center on paper", shortcut: "Ctrl+Shift+C", reason: arrange, run: () => void app.centerSelection() },
          { label: "Fit to paper", reason: arrange, run: () => void app.fitSelection() },
          "separator",
          { label: "Remove job from list", reason: jobId ? null : "Select a drawing first.", run: () => jobId && app.removeJob(jobId) },
        ],
      },
      {
        name: "View",
        items: [
          { label: "Fit paper in window", shortcut: "Ctrl+0", run: () => app.requestView({ kind: "fit-paper" }) },
          { label: "Fit reach in window", shortcut: "Ctrl+Alt+0", run: () => app.requestView({ kind: "fit-reach" }) },
          { label: "Zoom in", shortcut: "Ctrl+=", run: () => app.requestView({ kind: "zoom", factor: 1.25 }) },
          { label: "Zoom out", shortcut: "Ctrl+-", run: () => app.requestView({ kind: "zoom", factor: 0.8 }) },
          "separator",
          { heading: "Units" },
          ...UNITS.map((u) => ({ label: UNIT_NAMES[u], checked: s.units === u, radio: true, run: () => void app.setUnits(u) })),
          "separator",
          { label: "Show grid", checked: s.view.grid, run: () => app.toggleView("grid") },
          { label: "Show margins", checked: s.view.margins, run: () => app.toggleView("margins") },
          { label: "Show original artwork", checked: s.view.original, run: () => app.toggleView("original") },
        ],
      },
      {
        name: "Plotter",
        items: [
          {
            label: s.homing ? "Confirm Home (the pen is in the HOME corner)" : "Set Home",
            reason: disabledReason("setHome", s),
            run: () => void app.setHome(),
          },
          { label: "Plotter model…", reason: disabledReason("model", s), run: () => app.openModelDialog() },
          { label: "Move pen Home", reason: disabledReason("move", s), run: () => void app.movePenHome() },
          "separator",
          { label: "Trace outline", reason: disabledReason("trace", s), run: () => void app.trace() },
          { label: "Preview path", reason: disabledReason("preview", s), run: () => app.startPreview() },
          "separator",
          { label: "Start", shortcut: "Ctrl+Enter", reason: disabledReason("start", s), run: () => void app.startPlot() },
          { label: "Pause", shortcut: "Ctrl+Shift+P", reason: disabledReason("pause", s), run: () => app.pause() },
          { label: "Stop", reason: disabledReason("stop", s), run: () => app.stopPlot() },
        ],
      },
      {
        name: "Help",
        items: [
          { label: "Keyboard shortcuts", run: () => app.showDialog("shortcuts") },
          { label: "About Rosetta Plotter", run: () => app.showDialog("about") },
        ],
      },
    ];
  }

  render() {
    return html`<span class="brand">Rosetta Plotter</span>${this.menus().map(
      (menu) => html`<div class="top">
        <button
          class="title"
          aria-haspopup="menu"
          aria-expanded=${String(this.open === menu.name)}
          @click=${() => (this.open = this.open === menu.name ? null : menu.name)}
          @pointerenter=${() => {
            if (this.open && this.open !== menu.name) this.open = menu.name;
          }}
        >
          ${menu.name}
        </button>
        ${this.open === menu.name
          ? html`<div class="menu" role="menu" aria-label=${menu.name}>${menu.items.map((entry) => this.entry(entry))}</div>`
          : nothing}
      </div>`,
    )}`;
  }

  private entry(entry: Entry) {
    if (entry === "separator") return html`<hr />`;
    if ("heading" in entry) return html`<div class="heading">${entry.heading}</div>`;
    const reason = entry.reason ?? null;
    return html`<button
      role=${entry.checked === undefined ? "menuitem" : entry.radio ? "menuitemradio" : "menuitemcheckbox"}
      aria-checked=${entry.checked === undefined ? nothing : String(entry.checked)}
      aria-disabled=${reason ? "true" : "false"}
      title=${reason ?? ""}
      @click=${() => {
        this.open = null;
        if (reason) this.app.explain(reason);
        else entry.run();
      }}
    >
      <span>${entry.checked ? icon("check") : nothing}</span><span class="label">${entry.label}</span><span class="keys">${entry.shortcut ?? ""}</span>
    </button>`;
  }
}

customElements.define("rp-menubar", RpMenubar);
