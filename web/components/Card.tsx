import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  /** Extra classes for layout tweaks at the call site. */
  className?: string;
}

/**
 * Card — the base surface for the design system.
 * A soft, rounded, floating white panel. Compose everything else on top.
 */
export function Card({ children, className = "" }: CardProps) {
  return (
    <div
      className={
        "rounded-2xl border border-slate-200/70 bg-white/80 shadow-[var(--shadow-card)] " +
        "backdrop-blur-sm transition duration-200 " +
        className
      }
    >
      {children}
    </div>
  );
}
