import type { Order } from "@/lib/orders";
import type { AccentColor } from "@/lib/mockData";
import { accentClasses } from "@/lib/accents";
import { Card } from "./Card";
import { Badge } from "./Badge";

/** A labelled field row inside the order card. */
function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm text-slate-700">{children}</dd>
    </div>
  );
}

/** Format an ISO 8601 date/datetime deterministically (no locale drift). */
function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return iso;
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  return `${d} ${months[m - 1]} ${y}`;
}

export function OrderCard({
  order,
  accent,
}: {
  order: Order;
  accent: AccentColor;
}) {
  const c = accentClasses[accent];
  const confidencePct =
    order.extractionConfidence != null
      ? Math.round(order.extractionConfidence * 100)
      : null;

  return (
    <Card className="group flex flex-col overflow-hidden hover:-translate-y-1 hover:shadow-lg">
      {/* Colored accent bar */}
      <div className={`h-1.5 w-full ${c.bar}`} aria-hidden />

      <div className="flex flex-1 flex-col gap-4 p-5">
        {/* Header: company + tickers + date */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold leading-tight text-slate-900">
              {order.companyName}
            </h3>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {order.bseScripCode && (
                <Badge color={accent} withDot>
                  BSE {order.bseScripCode}
                </Badge>
              )}
              {order.nseSymbol && (
                <Badge color="sky">NSE {order.nseSymbol}</Badge>
              )}
            </div>
          </div>
          <time
            className="shrink-0 text-xs text-slate-400"
            dateTime={order.filedAt ?? undefined}
          >
            {formatDate(order.filedAt)}
          </time>
        </div>

        {/* Announcement headline — evidence straight from the filing */}
        {order.headline && (
          <p className="border-l-2 border-slate-200 pl-3 text-sm italic leading-snug text-slate-500">
            “{order.headline}”
          </p>
        )}

        {/* Value — the headline number */}
        <div className={`rounded-xl ${c.soft} px-4 py-3`}>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Order value
          </p>
          <p className={`text-2xl font-bold tracking-tight ${c.text}`}>
            {order.orderValueText ?? "—"}
          </p>
        </div>

        {/* The remaining extracted fields */}
        <dl className="grid grid-cols-2 gap-4">
          <Field label="Awarder">{order.awarder ?? "—"}</Field>
          <Field label="Duration">{order.durationText ?? "—"}</Field>
          <Field label="Target industry">
            {order.targetIndustry ? (
              <Badge color={accent}>{order.targetIndustry}</Badge>
            ) : (
              <span className="text-slate-400">Uncategorized</span>
            )}
          </Field>
          <Field label="Category">{order.category ?? "—"}</Field>
        </dl>

        {/* Description */}
        {order.description && (
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Description
            </dt>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">
              {order.description}
            </p>
          </div>
        )}

        {/* Evidence + provenance footer */}
        <div className="mt-auto space-y-2 border-t border-slate-100 pt-4">
          <div className="flex items-center justify-between gap-3">
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
              <svg
                className="h-3.5 w-3.5"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden
              >
                <path
                  fillRule="evenodd"
                  d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
                  clipRule="evenodd"
                />
              </svg>
              {order.sourceLabel ?? "Source filing"}
            </span>
            {order.attachmentUrl && (
              <a
                href={order.attachmentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={`inline-flex items-center gap-1 text-sm font-semibold ${c.text} hover:underline`}
              >
                View source filing
                <span aria-hidden>→</span>
              </a>
            )}
          </div>
          {(order.extractionModel || confidencePct != null) && (
            <p className="text-[11px] text-slate-400">
              Extracted
              {order.extractionModel ? ` by ${order.extractionModel}` : ""}
              {confidencePct != null ? ` · ${confidencePct}% confidence` : ""}
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
