import type { Order } from "./orders";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** Format an ISO 8601 date/datetime deterministically (no locale drift). */
export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

/**
 * Order value as JUST a number + its unit — never descriptive text.
 * INR orders show as "₹<n> Cr" (more decimals for sub-crore amounts so they
 * don't collapse to ₹0). For a foreign amount we didn't convert (USD/AED/…),
 * we keep only the leading "<currency> <number>", dropping qualifiers like
 * ", exclusive of taxes" or "(US Dollars …)".
 */
export function formatValue(order: Order): string {
  const cr = order.orderValueCrore;
  if (cr != null) {
    const digits = cr >= 1 ? 2 : 4;
    return `₹${cr.toLocaleString("en-IN", { maximumFractionDigits: digits })} Cr`;
  }
  const text = order.orderValueText;
  if (!text) return "—";
  // Split at the first clause boundary — ", <word>" (not a thousands comma) or
  // an opening paren — and keep the leading amount.
  return text.split(/,\s+|\s*\(/)[0].trim();
}

/** Duration as a number + unit (months). "—" when no month count was parsed. */
export function formatDuration(order: Order): string {
  if (order.durationMonths == null) return "—";
  return `${Math.round(order.durationMonths)} mo`;
}

/** Longer duration form for the detail view: "24 months · 2 yr". */
export function formatDurationLong(order: Order): string {
  if (order.durationMonths == null) return "—";
  const n = Math.round(order.durationMonths);
  const years = n % 12 === 0 && n >= 12 ? ` · ${n / 12} yr` : "";
  return `${n} month${n === 1 ? "" : "s"}${years}`;
}
