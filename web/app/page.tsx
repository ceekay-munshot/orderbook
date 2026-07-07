import { StatTile } from "@/components/StatTile";
import { OrderCard } from "@/components/OrderCard";
import { Badge } from "@/components/Badge";
import { mockOrders, mockStats } from "@/lib/mockData";

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

const statIcons = [icons.orders, icons.value, icons.companies, icons.latest];

export default function Home() {
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
            Mock data · scaffold
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
          {mockStats.map((stat, i) => (
            <StatTile
              key={stat.label}
              label={stat.label}
              value={stat.value}
              delta={stat.delta}
              positive={stat.positive}
              accent={stat.accent}
              icon={statIcons[i]}
            />
          ))}
        </section>

        {/* Orders */}
        <section aria-label="Latest orders">
          <div className="mb-4 flex items-end justify-between">
            <div>
              <h2 className="text-xl font-bold tracking-tight text-slate-900">
                Latest orders
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Newest first · across all tracked companies
              </p>
            </div>
            <Badge color="indigo">{mockOrders.length} shown</Badge>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
            {mockOrders.map((order) => (
              <OrderCard key={order.id} order={order} />
            ))}
          </div>
        </section>

        {/* Footer note */}
        <footer className="mt-12 border-t border-slate-200/70 pt-6 text-sm text-slate-400">
          Placeholder dashboard with mock data. Filters, search, and per-company
          history arrive in later steps. Data will be read live from Cloudflare
          D1 (binding <code className="text-slate-500">DB</code>).
        </footer>
      </main>
    </div>
  );
}
