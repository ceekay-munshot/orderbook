-- 0005_summary.sql
-- A short, plain-English summary of WHAT each order actually is (what's being
-- supplied / built / serviced, who awarded it, value + timeline when stated),
-- written from the filing/PDF text by the summarize pass. This is what the
-- dashboard shows instead of the SEBI regulatory boilerplate ("Pursuant to
-- Regulation 30 of SEBI (LODR) Regulations, 2015, ...").
--
-- Nullable; backfilled a few rows per run (cost-capped) and filled for new
-- orders during enrichment. Applied idempotently by ensure_schema().

ALTER TABLE orders ADD COLUMN summary TEXT;
