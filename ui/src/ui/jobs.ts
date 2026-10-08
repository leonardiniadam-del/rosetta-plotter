/** The Jobs panel (spec §2.5): imported files, placed by double-click or by dragging onto the paper. */
import { css, html, nothing } from "lit";
import type { JobInfo } from "../bridge/contract";
import { JOB_MIME } from "../canvas/interaction";
import { selectedPieces } from "../state/selectors";
import { AppElement } from "./base";
import { icon, type IconName } from "./icons";
import { controls } from "./styles";

function fileIcon(path: string): IconName {
  const lower = path.toLowerCase();
  if (lower.endsWith(".pdf") || lower.endsWith(".ai")) return "filePdf";
  return lower.endsWith(".svg") ? "fileVector" : "file";
}

interface Menu {
  jobId: string;
  x: number;
  y: number;
}

export class RpJobs extends AppElement {
  static properties = { menu: { state: true } };

  static styles = [
    controls,
    css`
      :host {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .row {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 3px 4px;
        border-radius: var(--radius);
      }
      .row:hover {
        background: var(--panel-raised);
      }
      .row.selected {
        background: rgba(59, 142, 234, 0.22);
      }
      .name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .check {
        display: inline-flex;
        color: var(--success);
      }
      .warn {
        display: inline-flex;
        color: var(--warning);
      }
      .empty {
        padding: 4px 0;
        color: var(--text-faint);
      }
      .menu {
        position: fixed;
        z-index: 40;
        display: flex;
        flex-direction: column;
        min-width: 160px;
        padding: 4px 0;
        background: var(--panel);
        border: 1px solid var(--line);
        box-shadow: var(--menu-shadow);
      }
      .menu button {
        justify-content: flex-start;
        height: 24px;
        padding: 0 12px;
        background: none;
        border: none;
        border-radius: 0;
      }
      .menu button:hover:not([aria-disabled="true"]) {
        background: var(--accent);
        color: #fff;
      }
    `,
  ];

  declare menu: Menu | null;

  constructor() {
    super();
    this.menu = null;
  }

  connectedCallback(): void {
    super.connectedCallback();
    window.addEventListener("pointerdown", this.closeMenu);
  }

  disconnectedCallback(): void {
    window.removeEventListener("pointerdown", this.closeMenu);
    super.disconnectedCallback();
  }

  private closeMenu = (event: Event): void => {
    const inMenu = event.composedPath().some((node) => node instanceof HTMLElement && node.classList.contains("menu"));
    if (this.menu && !inMenu) this.menu = null;
  };

  render() {
    const s = this.s;
    const selectedJobs = new Set(selectedPieces(s).map((p) => p.job_id));
    return html`<button @click=${() => this.app.importFiles()}>${icon("plus")}Import</button>
      ${s.jobs.length === 0 ? html`<div class="empty">Import SVG, PDF or AI files, or drop them on the window.</div>` : nothing}
      ${s.jobs.map((job) => this.row(job, selectedJobs.has(job.id)))} ${this.menu ? this.contextMenu(this.menu) : nothing}`;
  }

  private row(job: JobInfo, selected: boolean) {
    const copies = this.s.pieces.filter((p) => p.job_id === job.id).length;
    const issues = job.issues.map((i) => i.message).join("\n");
    return html`<div
      class="row ${selected ? "selected" : ""}"
      role="button"
      tabindex="0"
      draggable="true"
      title=${`${job.name}: double-click, or drag onto the paper, to place it. Delete removes it from the list.`}
      @dblclick=${() => this.app.placeJob(job.id)}
      @keydown=${(e: KeyboardEvent) => {
        if (e.key === "Enter") void this.app.placeJob(job.id);
        else if (e.key === "Delete") {
          e.stopPropagation(); // not the page's Delete (drawings on the paper)
          this.app.removeJob(job.id);
        }
      }}
      @dragstart=${(e: DragEvent) => {
        e.dataTransfer?.setData(JOB_MIME, job.id);
        if (e.dataTransfer) e.dataTransfer.effectAllowed = "copy";
      }}
      @contextmenu=${(e: MouseEvent) => {
        e.preventDefault();
        this.menu = { jobId: job.id, x: e.clientX, y: e.clientY };
      }}
    >
      ${icon(fileIcon(job.path))}<span class="name">${job.name}</span>
      ${copies ? html`<span class="check" title=${`${copies} on the paper`}>${icon("check")}</span>` : nothing}
      ${issues ? html`<span class="warn" title=${issues}>${icon("alert")}</span>` : nothing}
    </div>`;
  }

  private contextMenu(menu: Menu) {
    const job = this.s.jobs.find((j) => j.id === menu.jobId);
    if (!job) return nothing;
    const choose = (run: () => void) => () => {
      this.menu = null;
      run();
    };
    return html`<div class="menu" role="menu" style=${`left: ${menu.x}px; top: ${menu.y}px`}>
      <button role="menuitem" @click=${choose(() => void this.app.placeJob(job.id))}>Place</button>
      <button role="menuitem" @click=${choose(() => this.app.removeJob(job.id))}>Remove from list</button>
      <button
        role="menuitem"
        aria-disabled=${job.issues.length === 0 ? "true" : "false"}
        title=${job.issues.length === 0 ? "This file has no issues." : ""}
        @click=${choose(() =>
          job.issues.length === 0
            ? this.app.explain("This file has no issues.")
            : this.app.notify({ kind: "warning", message: job.issues.map((i) => i.message).join(" ") }),
        )}
      >Show issues</button>
    </div>`;
  }
}

customElements.define("rp-jobs", RpJobs);
