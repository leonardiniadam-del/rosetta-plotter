/** The Advanced settings (spec §4.7): checked in the page first, with the same wording as Python. */
import type { AdvancedValues, AppStart } from "../bridge/contract";

type Options = AppStart["advanced_options"];

/** Options where null means "Rosetta decides" (shown as Automatic). */
export const AUTOMATIC = ["pen_up", "speed_pendown"];

/** A starting number when Automatic is turned off. */
export const MANUAL_START: Record<string, number> = { pen_up: 60, speed_pendown: 25 };

export const CHOICE_LABELS: Record<string, Record<number, string>> = {
  reordering: { 0: "Join nearby ends only", 1: "Reorder", 2: "Reorder and reverse", 4: "Keep the file's order" },
  resolution: { 1: "Fine", 2: "Coarse (faster)" },
};

/** The first problem with these values, in the words Python uses (advanced_from_dict), or null. */
export function checkAdvanced(values: AdvancedValues, options: Options): string | null {
  for (const [name, value] of Object.entries(values)) {
    const label = options.labels[name] ?? name;
    if (name === "hiding") {
      if (typeof value !== "boolean") return `${label} must be on or off.`;
      continue;
    }
    if (value === null && AUTOMATIC.includes(name)) continue;
    if (typeof value !== "number" || !Number.isInteger(value)) return `${label} must be a whole number.`;
    const choices = options.choices[name];
    if (choices) {
      if (!choices.includes(value)) return `${label} must be one of ${choices.join(", ")}.`;
      continue;
    }
    const range = options.ranges[name];
    if (range && !(value >= range[0] && value <= range[1])) return `${label} must be from ${range[0]} to ${range[1]}.`;
  }
  return null;
}

export function changedAdvanced(draft: AdvancedValues, current: AdvancedValues): AdvancedValues {
  return Object.fromEntries(Object.entries(draft).filter(([name, value]) => value !== current[name]));
}
