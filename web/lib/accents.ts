import type { AccentColor } from "./mockData";

/**
 * Accent color -> concrete Tailwind class strings.
 *
 * Tailwind's compiler only keeps classes it can see as complete literal
 * strings, so we map each accent to full class names here (never build class
 * names by string concatenation elsewhere).
 */
export interface AccentClasses {
  /** Soft tinted surface. */
  soft: string;
  /** Text color on a soft/white surface. */
  text: string;
  /** Solid fill (e.g. an icon chip). */
  solid: string;
  /** Thin top border / accent bar. */
  bar: string;
  /** Ring / border for outlined elements. */
  ring: string;
}

/** Ordered accent cycle used across the cards / table / modal. */
export const ACCENT_CYCLE: AccentColor[] = [
  "indigo",
  "emerald",
  "amber",
  "rose",
  "violet",
  "sky",
];

/** Stable accent for an order, by id — so a given order looks the same in the
 * card grid, the table, and the modal. */
export function accentForId(id: number): AccentColor {
  return ACCENT_CYCLE[Math.abs(id) % ACCENT_CYCLE.length];
}

export const accentClasses: Record<AccentColor, AccentClasses> = {
  indigo: {
    soft: "bg-indigo-50",
    text: "text-indigo-700",
    solid: "bg-indigo-500",
    bar: "bg-indigo-500",
    ring: "ring-indigo-200",
  },
  emerald: {
    soft: "bg-emerald-50",
    text: "text-emerald-700",
    solid: "bg-emerald-500",
    bar: "bg-emerald-500",
    ring: "ring-emerald-200",
  },
  amber: {
    soft: "bg-amber-50",
    text: "text-amber-700",
    solid: "bg-amber-500",
    bar: "bg-amber-500",
    ring: "ring-amber-200",
  },
  rose: {
    soft: "bg-rose-50",
    text: "text-rose-700",
    solid: "bg-rose-500",
    bar: "bg-rose-500",
    ring: "ring-rose-200",
  },
  sky: {
    soft: "bg-sky-50",
    text: "text-sky-700",
    solid: "bg-sky-500",
    bar: "bg-sky-500",
    ring: "ring-sky-200",
  },
  violet: {
    soft: "bg-violet-50",
    text: "text-violet-700",
    solid: "bg-violet-500",
    bar: "bg-violet-500",
    ring: "ring-violet-200",
  },
};
