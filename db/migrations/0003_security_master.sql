-- 0003_security_master.sql
-- The company translator: BSE scrip code <-> NSE symbol <-> ISIN.
--
-- Built (ingestion/security_master.py) by joining two official public lists on
-- ISIN — the identifier both exchanges publish:
--   * NSE equity list  (SYMBOL, ISIN NUMBER, NAME OF COMPANY)
--   * BSE active-equity scrip list (SCRIP_CD, ISIN_NUMBER, Issuer_Name)
--
-- It lets us translate an order's BSE scrip code to its NSE symbol, which the
-- industry mapping (next step) is keyed by. Companies listed on BSE but not NSE
-- are kept with nse_symbol NULL — they simply stay "Unclassified" later.
--
-- Refreshed at most weekly (it changes rarely); see FORCE_MASTER_REBUILD.

CREATE TABLE IF NOT EXISTS security_master (
  bse_scrip_code TEXT PRIMARY KEY,        -- 6-char string, leading zeros kept
  isin           TEXT NOT NULL,           -- 12-char uppercase (the bridge key)
  nse_symbol     TEXT,                     -- NULL for BSE-only companies
  company_name   TEXT,
  source         TEXT,                     -- 'bse+nse' (matched) or 'bse' (BSE-only)
  updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_secmaster_isin ON security_master (isin);
CREATE INDEX IF NOT EXISTS idx_secmaster_nse  ON security_master (nse_symbol);
