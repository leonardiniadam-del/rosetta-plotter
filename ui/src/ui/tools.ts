/** The tools column (spec §2.3). A greyed-out tool says why in its tooltip, and in the strip when clicked. */
import { css, html, nothing } from "lit";
import { disabledReason } from "../state/reasons";
import type { Tool } from "../state/store";
import { AppElement } from "./base";
import { icon, type IconName } from "./icons";
import { controls } from "./styles";

interface ToolButton {
  label: string;
  iconName: IconName;
  pressed?: boolean;
  reason?: string | null;
  run: () => void;
}

export class RpTools extends AppElement {
  static styles = [
    controls,
    css`
      :host {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        padding: 6px 0;
      }
      button {
        width: var(--tool-size);
        height: var(--tool-size);
        padding: 0;
        justify-content: center;
        background: none;
        border-color: transparent;
      }
      svg.icon {
        width: 18px;
        height: 18px;
      }
      hr {
        width: 22px;
        margin: 4px 0;
        border: none;
        border-top: 1px solid var(--line);
      }
    `,
  ];

  private groups(): ToolButton[][] {
    const { app, s } = this;
    const tool = (name: Tool, label: string, iconName: IconName): ToolButton => ({
      label,
      iconName,
      pressed: s.tool === name,
      run: () => app.setTool(name),
    });
    const arrange = disabledReason("arrange", s);
    return [
      [
        tool("select", "Select (V)", "pointer"),
        tool("hand", "Hand (H, or hold Space)", "hand"),
        tool("zoom", "Zoom (Z; Alt-click zooms out)", "zoom"),
      ],
      [
        { ...tool("pen", "Move pen to point (P)", "crosshair"), reason: disabledReason("move", s) },
        {
          label: s.homing ? "Slide the pen to the HOME corner, then click again (Esc cancels)" : "Set Home",
          iconName: "home",
          pressed: s.homing,
          reason: disabledReason("setHome", s),
          run: () => void app.setHome(),
        },
      ],
      [
        tool("rotate", "Rotate (R): drag around the drawing; Shift snaps to 15°", "rotate"),
        { label: "Rotate paper 90° (Ctrl+Shift+R)", iconName: "rotatePaper", reason: disabledReason("rotatePaper", s), run: () => void app.rotatePaper() },
        { label: "Center on paper (Ctrl+Shift+C)", iconName: "center", reason: arrange, run: () => void app.centerSelection() },
        { label: "Duplicate (Ctrl+D)", iconName: "duplicate", reason: arrange, run: () => void app.duplicateSelection() },
        { label: "Delete (Del)", iconName: "trash", reason: arrange, run: () => void app.deleteSelection() },
      ],
    ];
  }

  render() {
    return this.groups().map(
      (group, index) =>
        html`${index > 0 ? html`<hr />` : nothing}${group.map((b) => {
          const reason = b.reason ?? null;
          return html`<button
            aria-label=${b.label}
            title=${reason ? `${b.label}: ${reason}` : b.label}
            aria-pressed=${b.pressed === undefined ? nothing : String(b.pressed)}
            aria-disabled=${reason ? "true" : "false"}
            @click=${() => (reason ? this.app.explain(reason) : b.run())}
          >
            ${icon(b.iconName)}
          </button>`;
        })}`,
    );
  }
}

customElements.define("rp-tools", RpTools);
