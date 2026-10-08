/** Keyboard shortcuts (Help › Keyboard shortcuts lists them; see app/shortcut-help.ts). */
import type { App } from "./app/app";
import { modalOpen } from "./state/selectors";
import type { Tool } from "./state/store";

const TOOL_KEYS: Record<string, Tool> = { v: "select", h: "hand", z: "zoom", r: "rotate", p: "pen" };
const ARROWS: Record<string, [number, number]> = { arrowleft: [-1, 0], arrowright: [1, 0], arrowup: [0, -1], arrowdown: [0, 1] };

function isTyping(event: KeyboardEvent): boolean {
  const target = event.composedPath()[0];
  return target instanceof HTMLElement && (["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName) || target.isContentEditable);
}

/** Handle one key press. True if it was a shortcut, so the caller stops the browser's own action for it. */
export function handleShortcut(app: App, event: KeyboardEvent): boolean {
  if (event.key === "Escape") {
    if (app.state.preview) app.endPreview();
    else if (app.state.homing) app.cancelHoming();
    else if (!modalOpen(app.state)) app.deselect();
    return false;
  }
  if (modalOpen(app.state)) return false; // a dialog is open: only Esc (above) does anything
  if (isTyping(event)) return false;
  const key = event.key.toLowerCase();
  if (event.ctrlKey || event.metaKey) {
    if (key === "i") void app.importFiles();
    else if (key === "d") void app.duplicateSelection();
    else if (key === "r" && event.shiftKey) void app.rotatePaper();
    else if (key === "r") void app.rotateSelectionBy(90);
    else if (key === "c" && event.shiftKey) void app.centerSelection();
    else if (key === "a" && event.shiftKey) app.deselect();
    else if (key === "a") app.selectAll();
    else if (key === "0") app.requestView({ kind: event.altKey ? "fit-reach" : "fit-paper" });
    else if (key === "=" || key === "+") app.requestView({ kind: "zoom", factor: 1.25 });
    else if (key === "-") app.requestView({ kind: "zoom", factor: 0.8 });
    else return false;
    return true;
  }
  if (event.altKey) return false;
  if (key === "delete" || key === "backspace") {
    if (app.state.selection.length > 0) void app.deleteSelection();
    return true;
  }
  if (key in ARROWS) {
    if (app.state.selection.length === 0) return false;
    const step = event.shiftKey ? 10 : 1;
    const [dx, dy] = ARROWS[key];
    void app.moveSelectionBy(dx * step, dy * step);
    return true;
  }
  if (!event.shiftKey && key in TOOL_KEYS) {
    app.setTool(TOOL_KEYS[key]);
    return true;
  }
  return false;
}

export function installShortcuts(app: App): () => void {
  const listener = (event: KeyboardEvent) => {
    if (handleShortcut(app, event)) event.preventDefault();
  };
  window.addEventListener("keydown", listener);
  return () => window.removeEventListener("keydown", listener);
}
