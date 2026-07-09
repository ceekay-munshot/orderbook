"use client";

import { useEffect } from "react";
import type { Order } from "@/lib/orders";
import { accentClasses, accentForId, accentHex } from "@/lib/accents";
import { formatDate, formatValue, formatDurationLong } from "@/lib/format";

/** Small solid icon (20×20 viewBox) — keeps the modal from importing an icon lib. */
function Icon({ d, className = "h-4 w-4" }: { d: string; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path fillRule="evenodd" d={d} clipRule="evenodd" />
    </svg>
  );
}

const ICON = {
  trending:
    "M12 7a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0V8.414l-4.293 4.293a1 1 0 01-1.414 0L8 10.414l-4.293 4.293a1 1 0 01-1.414-1.414l5-5a1 1 0 011.414 0L11 10.586 14.586 7H12z",
  clock:
    "M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z",
  building:
    "M4 4a2 2 0 012-2h8a2 2 0 012 2v14a1 1 0 110 2h-3a1 1 0 01-1-1v-2a1 1 0 00-1-1H9a1 1 0 00-1 1v2a1 1 0 01-1 1H4a1 1 0 110-2V4zm3 1h2v2H7V5zm2 4H7v2h2V9zm2-4h2v2h-2V5zm2 4h-2v2h2V9z",
  doc: "M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z",
  close:
    "M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z",
};

/** Darken a #rrggbb hex toward black by factor `f` (0..1). Deterministic, no
 * browser color-mix() dependency — safe as an inline gradient stop. */
function darken(hex: string, f = 0.52): string {
  const n = parseInt(hex.slice(1), 16);
  const r = Math.round(((n >> 16) & 255) * f);
  const g = Math.round(((n >> 8) & 255) * f);
  const b = Math.round((n & 255) * f);
  return `rgb(${r}, ${g}, ${b})`;
}

/** Strip the boilerplate regulatory lead-in from a filing so a reader sees what
 * the order actually IS. A stopgap for rows that don't yet have an AI `summary`;
 * once the ingest writes `order.summary`, that clean sentence is used instead. */
function cleanFilingText(text: string | null | undefined): string | null {
  if (!text) return null;
  let t = text.trim();
  // "Pursuant to Regulation 30 of SEBI (Listing Obligations and Disclosure
  //  Requirements) Regulations, 2015, ..."
  t = t.replace(/^pursuant to regulation\b[\s\S]*?regulations?,?\s*\d{4}\s*,?\s*/i, "");
  // "we are pleased/thrilled to announce/inform/intimate that ..."
  t = t.replace(/^(we|the company)\b[\s\S]*?\b(announce|inform|intimate|state|advise)\b[\s\S]*?that\s+/i, "");
  t = t.trim();
  if (!t) return null;
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/** A white translucent pill for the colored header. */
function HeaderChip({
  children,
  dot = false,
  muted = false,
}: {
  children: React.ReactNode;
  dot?: boolean;
  muted?: boolean;
}) {
  return (
    <span
      className={
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset backdrop-blur " +
        (muted
          ? "bg-white/10 text-white/70 ring-white/15"
          : "bg-white/20 text-white ring-white/30")
      }
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-white/90" aria-hidden />}
      {children}
    </span>
  );
}

function Detail({
  label,
  accentClass,
  children,
}: {
  label: string;
  accentClass: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className={`text-[11px] font-semibold uppercase tracking-wide ${accentClass}`}>
        {label}
      </dt>
      <dd className="mt-0.5 break-words text-sm font-medium text-slate-700">{children}</dd>
    </div>
  );
}

/**
 * Central detail modal for a single order. Opened by clicking a table row.
 *
 * Colored gradient header + accent tiles for a lively look; a single clamped
 * "filing summary" (no duplicate headline/description) keeps it short so it
 * fits without much scrolling. Closes on Escape, backdrop click, or ×.
 */
export function OrderModal({
  order,
  onClose,
}: {
  order: Order;
  onClose: () => void;
}) {
  const accent = accentForId(order.id);
  const c = accentClasses[accent];
  const hex = accentHex[accent];
  const classified =
    order.targetIndustry && order.targetIndustry !== "Unclassified";
  const hasMonths = order.durationMonths != null;
  // Prefer the AI-written order summary; fall back to the filing text with its
  // regulatory boilerplate stripped. One block only — never the raw quote twice.
  const summary =
    order.summary?.trim() || cleanFilingText(order.description ?? order.headline);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  return (
    <div
      className="ob-backdrop fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${order.companyName} order details`}
    >
      <div
        className="ob-modal relative flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl sm:max-h-[88vh] sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Colored gradient header */}
        <div
          className="relative px-6 pb-5 pt-6 text-white"
          style={{ background: `linear-gradient(135deg, ${hex} 0%, ${darken(hex)} 100%)` }}
        >
          <button
            onClick={onClose}
            aria-label="Close"
            className="absolute right-4 top-4 rounded-full p-1.5 text-white/80 transition hover:bg-white/20 hover:text-white"
          >
            <Icon d={ICON.close} className="h-5 w-5" />
          </button>
          <h2 className="pr-10 text-xl font-bold leading-tight sm:text-2xl">
            {order.companyName}
          </h2>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {order.bseScripCode && <HeaderChip dot>BSE {order.bseScripCode}</HeaderChip>}
            {order.nseSymbol && <HeaderChip dot>NSE {order.nseSymbol}</HeaderChip>}
            {classified ? (
              <HeaderChip>{order.targetIndustry}</HeaderChip>
            ) : (
              <HeaderChip muted>Unclassified</HeaderChip>
            )}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {/* Value + duration hero tiles */}
          <div className="grid grid-cols-2 gap-3">
            <div className={`rounded-2xl ${c.soft} p-4`}>
              <div className={`flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide ${c.text}`}>
                <Icon d={ICON.trending} className="h-3.5 w-3.5" />
                Order value
              </div>
              <p className={`mt-1 text-2xl font-extrabold tracking-tight ${c.text}`}>
                {formatValue(order)}
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-inset ring-slate-100">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                <Icon d={ICON.clock} className="h-3.5 w-3.5" />
                Duration
              </div>
              <p
                className={`mt-1 font-extrabold tracking-tight text-slate-800 ${
                  hasMonths ? "text-2xl" : "text-base leading-snug"
                }`}
              >
                {hasMonths ? formatDurationLong(order) : order.durationText ?? "—"}
              </p>
            </div>
          </div>

          {/* Awarder highlight */}
          {order.awarder && (
            <div className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-white p-3.5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${c.soft} ${c.text}`}>
                <Icon d={ICON.building} className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className={`text-[11px] font-semibold uppercase tracking-wide ${c.text}`}>
                  Awarded by
                </p>
                <p className="mt-0.5 text-sm font-medium leading-snug text-slate-700">
                  {order.awarder}
                </p>
              </div>
            </div>
          )}

          {/* Meta grid */}
          <dl className="grid grid-cols-3 gap-x-4 gap-y-3 rounded-2xl bg-slate-50/70 p-4">
            <Detail label="Filed" accentClass={c.text}>
              {formatDate(order.filedAt)}
            </Detail>
            <Detail label="Category" accentClass={c.text}>
              {order.category ?? "—"}
            </Detail>
            <Detail label="Exchange" accentClass={c.text}>
              {order.exchange ?? "—"}
            </Detail>
          </dl>

          {/* What the order is — full text, no truncation */}
          {summary && (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                What this order is
              </p>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">
                {summary}
              </p>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between gap-3 border-t border-slate-100 bg-white px-6 py-4">
          <span className="text-[11px] text-slate-400">
            {order.updatedAt ? `Updated ${formatDate(order.updatedAt)}` : ""}
          </span>
          {order.attachmentUrl ? (
            <a
              href={order.attachmentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-90"
              style={{ background: `linear-gradient(135deg, ${hex} 0%, ${darken(hex, 0.68)} 100%)` }}
            >
              <Icon d={ICON.doc} />
              Open source filing (PDF)
            </a>
          ) : (
            <span className="text-xs text-slate-400">No source PDF</span>
          )}
        </div>
      </div>
    </div>
  );
}
