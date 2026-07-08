import { StatTile } from "@/components/StatTile";
import { OrdersExplorer } from "@/components/OrdersExplorer";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { getOrders } from "@/lib/orders";

// Orders are read from D1 per request — never statically prerendered.
export const dynamic = "force-dynamic";

/* Inline icons (no icon dependency) — one per KPI tile. */
const icons = {
  orders: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h12a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6z" />
    </svg>
  ),
  value: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v.5a2.5 2.5 0 000 4.9V14a1 1 0 102 0v-.6a2.5 2.5 0 000-4.9V7z"
        clipRule="evenodd"
      />
    </svg>
  ),
  companies: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path
        fillRule="evenodd"
        d="M4 4a2 2 0 012-2h8a2 2 0 012 2v14H4V4zm3 2h2v2H7V6zm4 0h2v2h-2V6zM7 9h2v2H7V9zm4 0h2v2h-2V9zm-4 3h2v2H7v-2zm4 0h2v2h-2v-2z"
        clipRule="evenodd"
      />
    </svg>
  ),
  latest: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.5 2.5a1 1 0 001.414-1.414L11 9.586V6z"
        clipRule="evenodd"
      />
    </svg>
  ),
};

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

function formatCrore(total: number): string {
  return `₹${Math.round(total).toLocaleString("en-IN")} Cr`;
}

export default async function Home() {
  const orders = await getOrders();

  // KPI row derived from the real (or fallback) orders.
  const totalCrore = orders.reduce((sum, o) => sum + (o.orderValueCrore ?? 0), 0);
  const companies = new Set(orders.map((o) => o.companyName)).size;
  const latestFiledAt = orders.reduce<string | null>(
    (max, o) => (o.filedAt && (!max || o.filedAt > max) ? o.filedAt : max),
    null,
  );

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-slate-200/70 bg-white/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-xl text-lg font-black text-white shadow-md"
              style={{
                backgroundImage:
                  "linear-gradient(135deg, #6366f1 0%, #22d3ee 100%)",
              }}
            >
              O
            </div>
            <div>
              <p className="text-lg font-bold leading-none tracking-tight text-slate-900">
                Orderbook
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Indian order-book intelligence
              </p>
            </div>
          </div>
          <Badge color="emerald" withDot>
            Demo data
          </Badge>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {/* Intro */}
        <section className="mb-8">
          <p className="mb-2 text-sm font-semibold uppercase tracking-wider text-brand-600">
            Live order book
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            Every order win, across every company.
          </h1>
          <p className="mt-3 max-w-2xl text-base text-slate-600">
            We track order and contract wins disclosed by Indian listed
            companies on the BSE. Each order is read from its original filing and
            broken into five fields — always{" "}
            <span className="font-semibold text-slate-800">
              source- and evidence-backed
            </span>
            , never a black box.
          </p>
        </section>

        {/* KPI stat row */}
        <section
          aria-label="Key statistics"
          className="mb-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          <StatTile
            label="Orders tracked"
            value={String(orders.length)}
            hint="in the order book"
            accent="indigo"
            icon={icons.orders}
          />
          <StatTile
            label="Total order value"
            value={totalCrore > 0 ? formatCrore(totalCrore) : "—"}
            hint="sum of disclosed values"
            accent="emerald"
            icon={icons.value}
          />
          <StatTile
            label="Companies covered"
            value={String(companies)}
            hint="distinct issuers"
            accent="violet"
            icon={icons.companies}
          />
          <StatTile
            label="Latest filing"
            value={formatDate(latestFiledAt)}
            hint="most recent order"
            accent="rose"
            icon={icons.latest}
          />
        </section>

        {/* Orders — card grid or table view, with a click-through detail modal */}
        <section aria-label="Latest orders">
          {orders.length > 0 ? (
            <OrdersExplorer orders={orders} />
          ) : (
            <>
              <div className="mb-4">
                <h2 className="text-xl font-bold tracking-tight text-slate-900">
                  Latest orders
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Newest first · across all tracked companies
                </p>
              </div>
              <EmptyState />
            </>
          )}
        </section>

        {/* Footer note */}
        <footer className="mt-12 border-t border-slate-200/70 pt-6 text-sm text-slate-400">
          Reading orders from Cloudflare D1 (binding{" "}
          <code className="text-slate-500">DB</code>). Filters, search, and
          per-company history arrive in later steps.
        </footer>
      </main>
    </div>
  );
}

function EmptyState() {
  return (
    <Card className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-500">
        <svg className="h-6 w-6" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h12a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6z" />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-slate-800">No orders yet</h3>
      <p className="max-w-md text-sm text-slate-500">
        The order book is connected to D1 but empty. Run{" "}
        <code className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
          npm run db:seed:local
        </code>{" "}
        to load demo rows, or wait for the ingestion pipeline (Steps 3–5) to
        populate it.
      </p>
    </Card>
  );
}
