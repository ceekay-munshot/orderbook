import type { Order } from "@/lib/orders";
import { accentForId, accentHex } from "@/lib/accents";
import { Badge } from "./Badge";
import { formatDate, formatValue, formatDuration } from "@/lib/format";

/** A small PDF/source icon that links straight to the filing (stops the row
 * click from also opening the modal). */
function SourceLink({ url }: { url: string | null }) {
  if (!url) return <span className="text-slate-300">—</span>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      title="Open source filing (PDF)"
      aria-label="Open source filing (PDF)"
      className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-brand-500 transition hover:bg-brand-100 hover:text-brand-700"
    >
      <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
        <path
          fillRule="evenodd"
          d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
          clipRule="evenodd"
        />
      </svg>
    </a>
  );
}

const TH =
  "px-3 py-3 text-[11px] font-bold uppercase tracking-wider text-white first:rounded-tl-2xl last:rounded-tr-2xl";
/** Vertical divider between body cells (skips the first cell). */
const TD = "px-3 py-3 border-l border-slate-100 first:border-l-0";

/**
 * Colorful table view of every order. Gradient header, a per-row accent bar,
 * zebra striping, cell borders. Everything is centered except the left-aligned
 * company name; cells wrap so the whole table fits (no horizontal scroll).
 * Clicking a row opens the detail modal; the Source column links to the PDF.
 */
export function OrdersTable({
  orders,
  onSelect,
}: {
  orders: Order[];
  onSelect: (order: Order) => void;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200/70 shadow-[var(--shadow-card)]">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr
            style={{ backgroundImage: "linear-gradient(120deg,#6366f1 0%,#8b5cf6 55%,#0ea5e9 100%)" }}
          >
            <th className={`${TH} text-left`}>Company</th>
            <th className={`${TH} text-center`}>Date</th>
            <th className={`${TH} text-center`}>Order value</th>
            <th className={`${TH} text-center`}>Awarder</th>
            <th className={`${TH} text-center`}>Duration</th>
            <th className={`${TH} text-center`}>Target industry</th>
            <th className={`${TH} text-center`}>Source</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order, i) => {
            const accent = accentForId(order.id);
            const classified =
              order.targetIndustry && order.targetIndustry !== "Unclassified";
            return (
              <tr
                key={order.id}
                onClick={() => onSelect(order)}
                style={{ boxShadow: `inset 3px 0 0 ${accentHex[accent]}` }}
                className={
                  "cursor-pointer border-b border-slate-200/70 align-middle transition last:border-b-0 hover:bg-brand-50/60 " +
                  (i % 2 ? "bg-slate-50/50" : "bg-white/80")
                }
              >
                <td className={`${TD} text-left`}>
                  <div className="font-semibold leading-snug text-slate-900">
                    {order.companyName}
                  </div>
                  <div className="mt-0.5 text-xs text-slate-400">
                    {order.bseScripCode ? `BSE ${order.bseScripCode}` : ""}
                    {order.nseSymbol ? ` · NSE ${order.nseSymbol}` : ""}
                  </div>
                </td>
                <td className={`${TD} text-center whitespace-nowrap text-slate-500`}>
                  {formatDate(order.filedAt)}
                </td>
                <td className={`${TD} text-center font-bold tabular-nums text-emerald-700`}>
                  {formatValue(order)}
                </td>
                <td className={`${TD} text-center text-slate-600`}>
                  {order.awarder ?? "—"}
                </td>
                <td className={`${TD} text-center tabular-nums text-slate-600`}>
                  {formatDuration(order)}
                </td>
                <td className={`${TD} text-center`}>
                  {classified ? (
                    <Badge color={accent} className="whitespace-normal">
                      {order.targetIndustry}
                    </Badge>
                  ) : (
                    <span className="text-slate-400">Unclassified</span>
                  )}
                </td>
                <td className={`${TD} text-center`}>
                  <SourceLink url={order.attachmentUrl} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
