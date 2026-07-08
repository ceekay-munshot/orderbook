"use client";

import { useState } from "react";
import type { Order } from "@/lib/orders";
import { accentForId } from "@/lib/accents";
import { Badge } from "./Badge";
import { OrderCard } from "./OrderCard";
import { OrdersTable } from "./OrdersTable";
import { OrderModal } from "./OrderModal";

type View = "cards" | "table";

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

/**
 * Client wrapper for the orders section: a Cards ⟷ Table view toggle, plus the
 * detail modal that opens when a table row is clicked. The order data is fetched
 * on the server and passed in.
 */
export function OrdersExplorer({ orders }: { orders: Order[] }) {
  const [view, setView] = useState<View>("table");
  const [selected, setSelected] = useState<Order | null>(null);

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
        <div className="flex items-center gap-3">
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
          <Badge color="indigo">{orders.length} shown</Badge>
        </div>
      </div>

      {view === "cards" ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {orders.map((order) => (
            <OrderCard key={order.id} order={order} accent={accentForId(order.id)} />
          ))}
        </div>
      ) : (
        <OrdersTable orders={orders} onSelect={setSelected} />
      )}

      {selected && (
        <OrderModal order={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
