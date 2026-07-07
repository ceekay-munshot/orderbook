-- 0001_init.sql — orderbook schema (Cloudflare D1 / SQLite dialect).
--
-- Nothing is live yet, so this single clean migration defines the real schema.
-- Applied to LOCAL D1 with:  npm run db:migrate:local   (from /web)
--
-- Design principle: every order is source- and evidence-backed. We store the
-- original filing link (attachment_url), the raw extracted text fed to the LLM
-- (raw_text), the announcement headline, and extraction provenance
-- (extraction_model + extraction_confidence) so the UI can always show WHERE a
-- value came from.

CREATE TABLE IF NOT EXISTS orders (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  -- company identity (these are the join keys to industry_map, used in Step 6)
  company_name          TEXT NOT NULL,
  bse_scrip_code        TEXT,                 -- 6-char string, keep leading zeros
  nse_symbol            TEXT,
  isin                  TEXT,                 -- 12-char uppercase
  -- the 5 extracted fields
  order_value_text      TEXT,                 -- raw, e.g. 'INR 2500.0 Crore' or 'not specified'
  order_value_crore     REAL,                 -- parsed number in crore, NULL if not specified
  awarder               TEXT,                 -- who placed the order
  duration_text         TEXT,                 -- raw, e.g. '26.0 Months'
  duration_months       REAL,                 -- parsed
  target_industry       TEXT,                 -- filled from industry_map (Step 6)
  description           TEXT,
  -- evidence / provenance
  exchange              TEXT NOT NULL DEFAULT 'BSE',
  category              TEXT,                 -- BSE subcategory e.g. 'Award of Order / Receipt of Order'
  headline              TEXT,                 -- BSE announcement headline
  attachment_url        TEXT,                 -- link to the source PDF ('View attachment')
  source_label          TEXT,                 -- e.g. 'BSE Filing'
  raw_text              TEXT,                 -- extracted PDF text fed to the LLM (evidence)
  extraction_confidence REAL,                 -- 0..1
  extraction_model      TEXT,                 -- e.g. 'gpt-4o'
  -- identity / dedup / timestamps
  bse_announcement_id   TEXT,                 -- BSE NEWSID if available
  dedup_key             TEXT NOT NULL UNIQUE, -- stable hash so we never double-insert
  filed_at              TEXT,                 -- ISO 8601, when filed on BSE
  created_at            TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_orders_filed_at ON orders (filed_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_scrip    ON orders (bse_scrip_code);
CREATE INDEX IF NOT EXISTS idx_orders_isin     ON orders (isin);
CREATE INDEX IF NOT EXISTS idx_orders_industry ON orders (target_industry);

-- lookup table for the Stock Scan industry mapping; created now, POPULATED IN STEP 6 (leave empty)
CREATE TABLE IF NOT EXISTS industry_map (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  bse_scrip_code   TEXT,
  isin             TEXT,
  nse_symbol       TEXT,
  company_name     TEXT,
  name_normalized  TEXT,      -- lowercased/trimmed, for fuzzy name fallback
  industry         TEXT NOT NULL,
  sub_industry     TEXT
);
CREATE INDEX IF NOT EXISTS idx_map_scrip ON industry_map (bse_scrip_code);
CREATE INDEX IF NOT EXISTS idx_map_isin  ON industry_map (isin);
CREATE INDEX IF NOT EXISTS idx_map_name  ON industry_map (name_normalized);
