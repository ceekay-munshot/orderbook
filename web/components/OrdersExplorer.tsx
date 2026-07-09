"use client";

import { useMemo, useState } from "react";
import type { Order } from "@/lib/orders";
import { accentForId } from "@/lib/accents";
import { exportOrdersToExcel } from "@/lib/excel";
import { OrderCard } from "./OrderCard";
import { OrdersTable } from "./OrdersTable";
import { OrderModal } from "./OrderModal";

type View = "cards" | "table";

const VALUE_BUCKETS = [
  { id: "any", label: "Any value" },
  { id: "u100", label: "Under ₹100 Cr" },
  { id: "100_500", label: "₹100 – 500 Cr" },
  { id: "500_1000", label: "₹500 – 1,000 Cr" },
  { id: "o1000", label: "Over ₹1,000 Cr" },
];

const DATE_BUCKETS = [
  { id: "all", label: "All time", days: 0 },
  { id: "7", label: "Last 7 days", days: 7 },
  { id: "30", label: "Last 30 days", days: 30 },
  { id: "90", label: "Last 90 days", days: 90 },
  { id: "365", label: "Last 12 months", days: 365 },
];

function inValueBucket(cr: number | null, bucket: string): boolean {
  if (bucket === "any") return true;
  if (cr == null) return false;
  if (bucket === "u100") return cr < 100;
  if (bucket === "100_500") return cr >= 100 && cr < 500;
  if (bucket === "500_1000") return cr >= 500 && cr < 1000;
  if (bucket === "o1000") return cr >= 1000;
  return true;
}

function inDateBucket(filedAt: string | null, days: number): boolean {
  if (days === 0) return true;
  if (!filedAt) return false;
  const t = Date.parse(filedAt);
  if (Number.isNaN(t)) return false;
  return Date.now() - t <= days * 86_400_000;
}

function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={
        "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition " +
        (active
          ? "bg-brand-600 text-white shadow-sm"
          : "text-slate-500 hover:text-slate-800")
      }
    >
      {children}
    </button>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-brand-600">
        {label}
      </span>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 pr-8 text-sm font-medium text-slate-700 shadow-sm outline-none transition hover:border-slate-300 focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
        >
          {children}
        </select>
        <svg
          className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden
        >
          <path
            fillRule="evenodd"
            d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
            clipRule="evenodd"
          />
        </svg>
      </div>
    </label>
  );
}

/**
 * Client wrapper for the orders section: filters (industry / value / date), a
 * Cards ⟷ Table view toggle, an Excel export of the filtered rows, and the
 * detail modal that opens when a row is clicked. Order data is fetched on the
 * server and passed in; filtering is client-side.
 */
export function OrdersExplorer({ orders }: { orders: Order[] }) {
  const [view, setView] = useState<View>("table");
  const [selected, setSelected] = useState<Order | null>(null);
  const [industry, setIndustry] = useState("all");
  const [valueBucket, setValueBucket] = useState("any");
  const [dateBucket, setDateBucket] = useState("all");

  const industries = useMemo(() => {
    const set = new Set<string>();
    for (const o of orders) set.add(o.targetIndustry?.trim() || "Unclassified");
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [orders]);

  const days = DATE_BUCKETS.find((d) => d.id === dateBucket)?.days ?? 0;
  const filtered = useMemo(
    () =>
      orders.filter((o) => {
        const ind = o.targetIndustry?.trim() || "Unclassified";
        if (industry !== "all" && ind !== industry) return false;
        if (!inValueBucket(o.orderValueCrore, valueBucket)) return false;
        if (!inDateBucket(o.filedAt, days)) return false;
        return true;
      }),
    [orders, industry, valueBucket, dateBucket, days],
  );

  const active =
    industry !== "all" || valueBucket !== "any" || dateBucket !== "all";
  const clearFilters = () => {
    setIndustry("all");
    setValueBucket("any");
    setDateBucket("all");
  };

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900">
            Latest orders
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Newest first · across all tracked companies
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() =>
              exportOrdersToExcel(
                filtered,
                `orderbook-orders-${new Date().toISOString().slice(0, 10)}.xls`,
              )
            }
            className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
              <path
                fillRule="evenodd"
                d="M10 3a1 1 0 011 1v6.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 111.414-1.414L9 10.586V4a1 1 0 011-1z"
                clipRule="evenodd"
              />
              <path d="M4 14a1 1 0 011 1v1h10v-1a1 1 0 112 0v2a1 1 0 01-1 1H4a1 1 0 01-1-1v-2a1 1 0 011-1z" />
            </svg>
            Export to Excel
          </button>
          <div className="inline-flex rounded-xl border border-slate-200 bg-white/70 p-0.5 shadow-sm backdrop-blur">
            <ToggleButton active={view === "cards"} onClick={() => setView("cards")}>
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path d="M3 3h6v6H3V3zm8 0h6v6h-6V3zM3 11h6v6H3v-6zm8 0h6v6h-6v-6z" />
              </svg>
              Cards
            </ToggleButton>
            <ToggleButton active={view === "table"} onClick={() => setView("table")}>
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path
                  fillRule="evenodd"
                  d="M3 4a1 1 0 011-1h12a1 1 0 011 1v12a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm2 1v2h10V5H5zm10 4H5v2h10V9zm0 4H5v2h10v-2z"
                  clipRule="evenodd"
                />
              </svg>
              Table
            </ToggleButton>
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <div className="mb-5 rounded-2xl border border-slate-200/80 bg-white/70 p-4 shadow-[var(--shadow-card)] backdrop-blur">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <FilterSelect label="Industry" value={industry} onChange={setIndustry}>
            <option value="all">All industries</option>
            {industries.map((ind) => (
              <option key={ind} value={ind}>
                {ind}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect label="Order value" value={valueBucket} onChange={setValueBucket}>
            {VALUE_BUCKETS.map((b) => (
              <option key={b.id} value={b.id}>
                {b.label}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect label="Filed" value={dateBucket} onChange={setDateBucket}>
            {DATE_BUCKETS.map((b) => (
              <option key={b.id} value={b.id}>
                {b.label}
              </option>
            ))}
          </FilterSelect>
          <div className="flex items-center gap-3 sm:pb-2">
            <span className="whitespace-nowrap text-sm font-semibold text-slate-600">
              {filtered.length}
              <span className="font-normal text-slate-400">
                {" "}
                of {orders.length}
              </span>
            </span>
            {active && (
              <button
                onClick={clearFilters}
                className="whitespace-nowrap rounded-lg px-2.5 py-1 text-xs font-semibold text-brand-600 transition hover:bg-brand-50"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-2xl border border-slate-200/70 bg-white/70 px-6 py-14 text-center shadow-sm">
          <p className="text-sm font-semibold text-slate-700">No orders match these filters</p>
          <button
            onClick={clearFilters}
            className="mt-3 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-brand-700"
          >
            Clear filters
          </button>
        </div>
      ) : view === "cards" ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((order) => (
            <OrderCard key={order.id} order={order} accent={accentForId(order.id)} />
          ))}
        </div>
      ) : (
        <OrdersTable orders={filtered} onSelect={setSelected} />
      )}

      {selected && (
        <OrderModal order={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
