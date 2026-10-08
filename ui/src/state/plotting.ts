/** Small facts about plotting that several parts of the page use. */
import type { PlotProgress } from "../bridge/contract";

/** The plot states where nothing is running (bridge.md "Plot states"). */
export const AT_REST = ["idle", "ready", "done"];

/** "4:10", or "1:02:05" past an hour. */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** How far through the whole plot (0–1), from the time left. */
export function overallFraction(totalSeconds: number, progress: PlotProgress | null): number {
  if (!progress) return 0;
  if (!(totalSeconds > 0)) return 1;
  return Math.min(1, Math.max(0, 1 - progress.seconds_left / totalSeconds));
}
