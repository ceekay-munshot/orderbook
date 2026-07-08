"use client";

import { useEffect } from "react";
import type { Order } from "@/lib/orders";
import { accentClasses, accentForId } from "@/lib/accents";
import { Badge } from "./Badge";
import { formatDate, formatValue, formatDurationLong } from "@/lib/format";

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </dt>
      <dd className="mt-0.5 break-words text-sm text-slate-700">{children}</dd>
    </div>
  );
}

/**
 * Central detail modal for a single order. Opened by clicking a table row.
 * Everything the card/table omits lives here — headline, description,
 * verification & evidence, provenance, and a link to the source PDF.
 *
 * Closes on Escape, backdrop click, or the × button; locks body scroll while open.
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
  const classified =
    order.targetIndustry && order.targetIndustry !== "Unclassified";

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
      className="ob-backdrop fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${order.companyName} order details`}
    >
      <div
        className="ob-modal relative flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl sm:max-h-[88vh] sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`h-1.5 w-full ${c.bar}`} aria-hidden />

        {/* Header */}
        <div className={`flex items-start justify-between gap-4 ${c.soft} px-6 pb-5 pt-5`}>
          <div className="min-w-0">
            <h2 className="text-xl font-bold leading-tight text-slate-900">
              {order.companyName}
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {order.bseScripCode && (
                <Badge color={accent} withDot>
                  BSE {order.bseScripCode}
                </Badge>
              )}
              {order.nseSymbol && <Badge color="sky">NSE {order.nseSymbol}</Badge>}
              {classified ? (
                <Badge color={accent}>{order.targetIndustry}</Badge>
              ) : (
                <span className="text-xs font-medium text-slate-400">
                  Unclassified
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded-full p-1.5 text-slate-400 transition hover:bg-white/80 hover:text-slate-700"
          >
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
          {/* Value + duration hero — number + unit only */}
          <div className="grid grid-cols-2 gap-3">
            <div className={`rounded-2xl ${c.soft} px-4 py-3`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Order value
              </p>
              <p className={`mt-0.5 text-2xl font-bold tracking-tight ${c.text}`}>
                {formatValue(order)}
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Duration
              </p>
              <p className="mt-0.5 text-2xl font-bold tracking-tight text-slate-800">
                {order.durationMonths != null
                  ? formatDurationLong(order)
                  : order.durationText ?? "—"}
              </p>
            </div>
          </div>

          {/* Headline */}
          {order.headline && (
            <p className="border-l-2 border-slate-200 pl-3 text-sm italic leading-snug text-slate-500">
              “{order.headline}”
            </p>
          )}

          {/* Field grid */}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
            <Detail label="Awarder">{order.awarder ?? "—"}</Detail>
            <Detail label="Filed">{formatDate(order.filedAt)}</Detail>
            <Detail label="Category">{order.category ?? "—"}</Detail>
            <Detail label="Exchange">{order.exchange ?? "—"}</Detail>
            <Detail label="ISIN">{order.isin ?? "—"}</Detail>
            <Detail label="Industry">{order.targetIndustry ?? "Unclassified"}</Detail>
          </dl>

          {/* Description */}
          {order.description && (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Description
              </p>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">
                {order.description}
              </p>
            </div>
          )}

        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-6 py-4">
          <span className="text-[11px] text-slate-400">
            {order.updatedAt ? `Updated ${formatDate(order.updatedAt)}` : ""}
          </span>
          {order.attachmentUrl ? (
            <a
              href={order.attachmentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={`inline-flex items-center gap-2 rounded-xl ${c.solid} px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-90`}
            >
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path
                  fillRule="evenodd"
                  d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
                  clipRule="evenodd"
                />
              </svg>
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
