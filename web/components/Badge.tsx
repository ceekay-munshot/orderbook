import type { ReactNode } from "react";
import type { AccentColor } from "@/lib/mockData";
import { accentClasses } from "@/lib/accents";

interface BadgeProps {
  children: ReactNode;
  /** Accent color; defaults to the brand indigo. */
  color?: AccentColor;
  /** Optional leading dot for a chip-like look. */
  withDot?: boolean;
  className?: string;
}

/**
 * Badge — small pill for labels, categories, and tickers.
 * Uses the shared accent palette so colors stay consistent app-wide.
 */
export function Badge({
  children,
  color = "indigo",
  withDot = false,
  className = "",
}: BadgeProps) {
  const c = accentClasses[color];
  return (
    <span
      className={
        `inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ` +
        `${c.soft} ${c.text} ring-1 ring-inset ${c.ring} ${className}`
      }
    >
      {withDot && (
        <span className={`h-1.5 w-1.5 rounded-full ${c.solid}`} aria-hidden />
      )}
      {children}
    </span>
  );
}
