-- 0004_full_stockscans.sql
-- Support the FULL stockscans.in classification (5,800+ companies, ~half of them
-- BSE-listed) instead of the ~951 daksham subset.
--
-- 1) security_master gains the company's BSE TICKER symbol (BSE's own scrip_id,
--    e.g. 500002 -> "ABB"). stockscans keys BSE companies by ticker ("BSE:ABB"),
--    NOT by the 6-digit scrip code, so we need the ticker to join BSE-only
--    companies (which have no NSE symbol) to their industry.
-- 2) industry_map gains `source` (which mapping built it) and `updated_at` (so
--    the full pull can be cached for a few days instead of re-fetched every run).
--
-- ALTER ADD COLUMN can't take a non-constant default in SQLite, so updated_at is
-- nullable here and written explicitly (datetime('now')) on every rebuild.
-- Applied idempotently by ensure_schema() — "duplicate column" is ignored.

ALTER TABLE security_master ADD COLUMN bse_symbol TEXT;
CREATE INDEX IF NOT EXISTS idx_secmaster_bsesym ON security_master (bse_symbol);

ALTER TABLE industry_map ADD COLUMN source TEXT;
ALTER TABLE industry_map ADD COLUMN updated_at TEXT;
