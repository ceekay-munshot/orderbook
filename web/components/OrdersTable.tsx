import type { Order } from "@/lib/orders";
import { accentForId } from "@/lib/accents";
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
      className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-brand-50 hover:text-brand-600"
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
  "px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400";

/**
 * Dense, sortable-looking table view of every order. Clicking a row opens the
 * detail modal; the Source column links straight to the filing PDF. Value and
 * Duration are shown as numbers with units (₹… Cr, N mo), not raw text.
 */
export function OrdersTable({
  orders,
  onSelect,
}: {
  orders: Order[];
  onSelect: (order: Order) => void;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200/70 bg-white/80 shadow-[var(--shadow-card)] backdrop-blur-sm">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200/70">
              <th className={TH}>Company</th>
              <th className={TH}>Date</th>
              <th className={`${TH} text-right`}>Order value</th>
              <th className={TH}>Awarder</th>
              <th className={`${TH} text-right`}>Duration</th>
              <th className={TH}>Target industry</th>
              <th className={`${TH} text-center`}>Source</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => {
              const accent = accentForId(order.id);
              const classified =
                order.targetIndustry &&
                order.targetIndustry !== "Unclassified";
              return (
                <tr
                  key={order.id}
                  onClick={() => onSelect(order)}
                  className="cursor-pointer border-b border-slate-100 transition last:border-0 hover:bg-slate-50/80"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">
                      {order.companyName}
                    </div>
                    <div className="mt-0.5 text-xs text-slate-400">
                      {order.bseScripCode ? `BSE ${order.bseScripCode}` : ""}
                      {order.nseSymbol ? ` · NSE ${order.nseSymbol}` : ""}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                    {formatDate(order.filedAt)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-slate-900">
                    {formatValue(order)}
                  </td>
                  <td className="max-w-[15rem] truncate px-4 py-3 text-slate-600">
                    {order.awarder ?? "—"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-600">
                    {formatDuration(order)}
                  </td>
                  <td className="px-4 py-3">
                    {classified ? (
                      <Badge color={accent}>{order.targetIndustry}</Badge>
                    ) : (
                      <span className="text-slate-400">Unclassified</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <SourceLink url={order.attachmentUrl} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
