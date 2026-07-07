-- 0002_pdf_checked.sql
-- Tracks whether the PDF-enrichment step has already tried a given order, so
-- repeat runs don't re-download the same PDFs (which costs Firecrawl/OpenAI
-- credits). 0 = not tried yet, 1 = tried (success OR fail).
--
-- Applied idempotently by ingestion/main.py's ensure_schema(): the ALTER errors
-- with "duplicate column" once the column exists, which is caught and ignored.

ALTER TABLE orders ADD COLUMN pdf_checked INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_orders_pdf_checked ON orders (pdf_checked);
