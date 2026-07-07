import type { ReactNode } from "react";
import type { AccentColor } from "@/lib/mockData";
import { accentClasses } from "@/lib/accents";
import { Card } from "./Card";

interface StatTileProps {
  label: string;
  value: string;
  /** Small caption under the value (e.g. a fact or a trend note). */
  hint?: string;
  /** Optional trend direction — adds a colored arrow. Omit for a neutral caption. */
  trend?: "up" | "down";
  accent?: AccentColor;
  icon?: ReactNode;
}

/**
 * StatTile — a single colorful KPI in the dashboard stat row.
 * Big value, small label, optional caption/trend, and a tinted icon chip.
 */
export function StatTile({
  label,
  value,
  hint,
  trend,
  accent = "indigo",
  icon,
}: StatTileProps) {
  const c = accentClasses[accent];
  const hintColor =
    trend === "up"
      ? "text-emerald-600"
      : trend === "down"
        ? "text-rose-600"
        : "text-slate-400";
  const arrow = trend === "up" ? "▲ " : trend === "down" ? "▼ " : "";
  return (
    <Card className="p-5 hover:-translate-y-0.5 hover:shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
            {value}
          </p>
        </div>
        {icon && (
          <div
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${c.soft} ${c.text}`}
          >
            {icon}
          </div>
        )}
      </div>
      {hint && (
        <p className={`mt-3 text-xs font-medium ${hintColor}`}>
          {arrow}
          {hint}
        </p>
      )}
    </Card>
  );
}
