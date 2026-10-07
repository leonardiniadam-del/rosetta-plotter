import { css } from "lit";

/** Base styles for controls inside components' shadow roots (theme.css can't reach in there). */
export const controls = css`
  :host {
    font: var(--font-size) / 1.4 var(--font);
    color: var(--text);
  }
  button,
  select,
  input {
    font: inherit;
    color: var(--text);
  }
  button {
    height: var(--control-height);
    padding: 0 8px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: var(--panel-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    cursor: default;
  }
  button:hover:not([aria-disabled="true"]) {
    border-color: var(--text-faint);
  }
  button.icon {
    width: var(--control-height);
    padding: 0;
    justify-content: center;
  }
  button.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }
  button[aria-pressed="true"] {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }
  [aria-disabled="true"],
  :disabled {
    opacity: 0.45;
  }
  select,
  input {
    height: var(--control-height);
    padding: 0 6px;
    box-sizing: border-box;
    background: var(--panel-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius);
  }
  input[type="range"] {
    padding: 0;
    border: none;
    background: none;
  }
  input[aria-invalid="true"] {
    border-color: var(--danger);
  }
  :focus-visible {
    outline: 1px solid var(--accent);
    outline-offset: 1px;
  }
  .dim {
    color: var(--text-dim);
  }
  .faint {
    color: var(--text-faint);
  }
  svg.icon {
    width: 16px;
    height: 16px;
    flex: none;
  }
`;
