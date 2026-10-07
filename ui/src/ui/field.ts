/**
 * A number box: a length in the chosen units, a percentage, or an angle. Enter or leaving the box
 * commits with a "commit" event whose detail is the value (mm, a factor, or degrees). Esc, or text it
 * can't read, puts the old value back.
 */
import { css, html, LitElement } from "lit";
import { formatAngle, formatLength, formatPercent, parseAngle, parseLength, parsePercent, type Units } from "../geometry/units";
import { controls } from "./styles";

export type FieldKind = "length" | "percent" | "angle";

export class RpField extends LitElement {
  static properties = {
    value: { type: Number },
    kind: {},
    units: {},
    label: {},
    tip: {},
    disabled: { type: Boolean },
    readonly: { type: Boolean },
    invalid: { state: true },
  };

  static styles = [
    controls,
    css`
      :host {
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      label {
        color: var(--text-dim);
      }
      input {
        width: 64px;
        text-align: right;
      }
    `,
  ];

  declare value: number;
  declare kind: FieldKind;
  declare units: Units;
  declare label: string;
  declare tip: string;
  declare disabled: boolean;
  declare readonly: boolean;
  declare invalid: boolean;

  constructor() {
    super();
    this.value = 0;
    this.kind = "length";
    this.units = "in";
    this.label = "";
    this.tip = "";
    this.disabled = false;
    this.readonly = false;
    this.invalid = false;
  }

  private format(): string {
    if (this.kind === "percent") return formatPercent(this.value);
    if (this.kind === "angle") return formatAngle(this.value);
    return formatLength(this.value, this.units);
  }

  private parse(text: string): number | null {
    if (this.kind === "percent") return parsePercent(text);
    if (this.kind === "angle") return parseAngle(text);
    return parseLength(text, this.units);
  }

  private commit(input: HTMLInputElement): void {
    const shown = this.format();
    // Untouched text, or a box that can't be edited: nothing to send (the shown value is rounded).
    if (this.readonly || this.disabled || input.value.trim() === shown) {
      input.value = shown;
      this.invalid = false;
      return;
    }
    const value = this.parse(input.value);
    if (value === null) {
      this.invalid = true;
      input.value = shown;
      return;
    }
    this.invalid = false;
    if (Math.abs(value - this.value) > 1e-9) this.dispatchEvent(new CustomEvent("commit", { detail: value }));
    input.value = this.format();
  }

  private onKey(event: KeyboardEvent): void {
    const input = event.target as HTMLInputElement;
    if (event.key === "Enter") {
      this.commit(input);
      input.dataset.committed = "1";
      input.blur();
    } else if (event.key === "Escape") {
      input.value = this.format();
      this.invalid = false;
      input.dataset.committed = "1";
      input.blur();
    }
  }

  private onBlur(event: FocusEvent): void {
    const input = event.target as HTMLInputElement;
    if (input.dataset.committed) {
      delete input.dataset.committed;
      return;
    }
    this.commit(input);
  }

  render() {
    return html`${this.label ? html`<label for="f">${this.label}</label>` : ""}<input
        id="f"
        .value=${this.format()}
        ?disabled=${this.disabled}
        ?readonly=${this.readonly}
        title=${this.tip}
        aria-label=${this.label || this.tip}
        aria-invalid=${this.invalid ? "true" : "false"}
        @keydown=${this.onKey}
        @focus=${(e: FocusEvent) => delete (e.target as HTMLInputElement).dataset.committed}
        @blur=${this.onBlur}
        @input=${() => (this.invalid = false)}
      />`;
  }
}

customElements.define("rp-field", RpField);
