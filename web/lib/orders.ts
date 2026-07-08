import { getCloudflareContext } from "@opennextjs/cloudflare";
import { mockOrders } from "./mockData";

/**
 * The camelCase order shape the UI consumes. Mirrors the `orders` table in
 * db/migrations/0001_init.sql (snake_case), minus `raw_text` — that evidence
 * blob is stored in D1 but not loaded in the newest-first list query (it's for
 * a future per-order detail view). Provenance we DO surface on the card:
 * `extractionModel` + `extractionConfidence`, plus the source `attachmentUrl`.
 */
export interface Order {
  id: number;
  // company identity (join keys to industry_map in Step 6)
  companyName: string;
  bseScripCode: string | null;
  nseSymbol: string | null;
  isin: string | null;
  // the 5 extracted fields
  orderValueText: string | null;
  orderValueCrore: number | null;
  awarder: string | null;
  durationText: string | null;
  durationMonths: number | null;
  targetIndustry: string | null;
  description: string | null;
  // evidence / provenance
  exchange: string;
  category: string | null;
  headline: string | null;
  attachmentUrl: string | null;
  sourceLabel: string | null;
  extractionConfidence: number | null;
  extractionModel: string | null;
  // identity / dedup / timestamps
  bseAnnouncementId: string | null;
  dedupKey: string;
  filedAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

/** Raw snake_case row as stored in D1. */
interface OrderRow {
  id: number;
  company_name: string;
  bse_scrip_code: string | null;
  nse_symbol: string | null;
  isin: string | null;
  order_value_text: string | null;
  order_value_crore: number | null;
  awarder: string | null;
  duration_text: string | null;
  duration_months: number | null;
  target_industry: string | null;
  description: string | null;
  exchange: string;
  category: string | null;
  headline: string | null;
  attachment_url: string | null;
  source_label: string | null;
  extraction_confidence: number | null;
  extraction_model: string | null;
  bse_announcement_id: string | null;
  dedup_key: string;
  filed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** Columns loaded for the list view (everything except the large raw_text blob). */
const SELECT_COLUMNS = [
  "id",
  "company_name",
  "bse_scrip_code",
  "nse_symbol",
  "isin",
  "order_value_text",
  "order_value_crore",
  "awarder",
  "duration_text",
  "duration_months",
  "target_industry",
  "description",
  "exchange",
  "category",
  "headline",
  "attachment_url",
  "source_label",
  "extraction_confidence",
  "extraction_model",
  "bse_announcement_id",
  "dedup_key",
  "filed_at",
  "created_at",
  "updated_at",
].join(", ");

/**
 * Minimal D1 surface we actually use. Declared locally (rather than pulling in
 * the global `@cloudflare/workers-types`, which clashes with Next's DOM lib) so
 * the app stays hermetic. Run `npm run cf-typegen` if you want full binding
 * types generated into cloudflare-env.d.ts.
 */
interface D1ResultLike<T> {
  results: T[];
}
interface D1PreparedStatementLike {
  all<T = Record<string, unknown>>(): Promise<D1ResultLike<T>>;
}
interface D1DatabaseLike {
  prepare(query: string): D1PreparedStatementLike;
}

function mapRow(r: OrderRow): Order {
  return {
    id: r.id,
    companyName: r.company_name,
    bseScripCode: r.bse_scrip_code,
    nseSymbol: r.nse_symbol,
    isin: r.isin,
    orderValueText: r.order_value_text,
    orderValueCrore: r.order_value_crore,
    awarder: r.awarder,
    durationText: r.duration_text,
    durationMonths: r.duration_months,
    targetIndustry: r.target_industry,
    description: r.description,
    exchange: r.exchange,
    category: r.category,
    headline: r.headline,
    attachmentUrl: r.attachment_url,
    sourceLabel: r.source_label,
    extractionConfidence: r.extraction_confidence,
    extractionModel: r.extraction_model,
    bseAnnouncementId: r.bse_announcement_id,
    dedupKey: r.dedup_key,
    filedAt: r.filed_at,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  };
}

/** Result of {@link getOrders}: the rows plus whether they came from live D1
 * (true) or the demo fallback (false), so the UI can label the source honestly. */
export interface OrdersResult {
  orders: Order[];
  isLive: boolean;
}

/**
 * Read all orders from Cloudflare D1 (via the `DB` binding), newest first.
 *
 * Falls back to demo mock data ONLY when the binding isn't available (e.g.
 * plain `next dev` with no Cloudflare context, or a build-time context where
 * `getCloudflareContext()` throws) — so the app always renders. A reachable but
 * empty table returns `[]` with `isLive: true` (clean empty state), NOT the mock.
 */
export async function getOrders(): Promise<OrdersResult> {
  try {
    const { env } = await getCloudflareContext({ async: true });
    const db = (env as { DB?: D1DatabaseLike }).DB;
    if (!db) return { orders: mockOrders, isLive: false };
    const { results } = await db
      .prepare(
        `SELECT ${SELECT_COLUMNS} FROM orders ORDER BY filed_at DESC, id DESC`,
      )
      .all<OrderRow>();
    return { orders: results.map(mapRow), isLive: true };
  } catch (err) {
    console.warn(
      "[orders] D1 binding unavailable — falling back to demo data.",
      err,
    );
    return { orders: mockOrders, isLive: false };
  }
}
