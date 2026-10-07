/** Lengths: everything inside the app is millimetres; the page shows inches, millimetres or centimetres. */
export type Units = "in" | "mm" | "cm";

export const UNITS: readonly Units[] = ["in", "mm", "cm"];
export const UNIT_NAMES: Record<Units, string> = { in: "Inches", mm: "Millimeters", cm: "Centimeters" };
export const MM_PER: Record<Units, number> = { in: 25.4, mm: 1, cm: 10 };
const DECIMALS: Record<Units, number> = { in: 2, mm: 1, cm: 2 };

export function toUnits(mm: number, units: Units): number {
  return mm / MM_PER[units];
}

/** "3.25", or "3.25 in" with the unit; rounded for the units, never "-0.00". */
export function formatLength(mm: number, units: Units, withUnit = false): string {
  const digits = DECIMALS[units];
  const rounded = Number(toUnits(mm, units).toFixed(digits));
  const text = (rounded === 0 ? 0 : rounded).toFixed(digits);
  return withUnit ? `${text} ${units}` : text;
}

const LENGTH = /^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(in|inch|inches|"|mm|cm)?\s*$/i;

/** A typed length in mm: "2", "2 in", '2"', "50mm", "5 cm". A bare number is in the display units. */
export function parseLength(text: string, units: Units): number | null {
  const match = LENGTH.exec(text);
  if (!match) return null;
  const value = Number(match[1]);
  if (!Number.isFinite(value)) return null;
  const suffix = (match[2] ?? "").toLowerCase();
  const unit: Units = suffix === "" ? units : suffix === "mm" ? "mm" : suffix === "cm" ? "cm" : "in";
  return value * MM_PER[unit];
}

const NUMBER = /^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(%|°|deg)?\s*$/i;

/** "50" or "50%" → 0.5. Null if unreadable or not above zero. */
export function parsePercent(text: string): number | null {
  const match = NUMBER.exec(text);
  if (!match || (match[2] && match[2] !== "%")) return null;
  const value = Number(match[1]) / 100;
  return Number.isFinite(value) && value > 0 ? value : null;
}

/** "30", "30°" or "-90" → degrees in [0, 360). */
export function parseAngle(text: string): number | null {
  const match = NUMBER.exec(text);
  if (!match || match[2] === "%") return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? normalizeAngle(value) : null;
}

/** Degrees in [0, 360); never -0. */
export function normalizeAngle(degrees: number): number {
  const value = degrees % 360;
  if (value < 0) return value + 360;
  return value === 0 ? 0 : value;
}

export function formatPercent(scale: number): string {
  return `${Number((scale * 100).toFixed(1))}%`;
}

export function formatAngle(degrees: number): string {
  return `${normalizeAngle(Number(normalizeAngle(degrees).toFixed(1)))}°`;
}
