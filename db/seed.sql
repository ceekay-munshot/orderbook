-- ============================================================================
-- db/seed.sql — DEMO SEED DATA (not real filings).
--
-- 5 plausible sample orders so the dashboard renders real rows from D1 during
-- development. Load into LOCAL D1 with:  npm run db:seed:local   (from /web)
--
-- These are hand-written demo rows — remove/replace once real BSE ingestion
-- (Steps 3-5) is populating the table. dedup_key follows the write contract:
--   prefer bse_announcement_id; else sha1("scrip|filed_at|headline").
-- Row 4 (KEC) intentionally has no announcement id + a NULL order value to
-- exercise the sha1 dedup path and the "not specified" value case.
-- ============================================================================

INSERT OR IGNORE INTO orders (
  company_name, bse_scrip_code, nse_symbol, isin,
  order_value_text, order_value_crore, awarder, duration_text, duration_months,
  target_industry, description,
  exchange, category, headline, attachment_url, source_label, raw_text,
  extraction_confidence, extraction_model,
  bse_announcement_id, dedup_key, filed_at
) VALUES
-- 1) BHEL (client example) — Power / Capital Goods
(
  'Bharat Heavy Electricals Limited', '500103', 'BHEL', 'INE257A01026',
  'INR 1,240.00 Crore', 1240.0, 'NTPC Limited', '28.0 Months', 28.0,
  'Capital Goods - Electrical Equipment',
  'Supply and installation of flue-gas desulphurisation (FGD) systems across two thermal power units.',
  'BSE', 'Award of Order / Receipt of Order',
  'BHEL bags order worth Rs 1,240 crore from NTPC for FGD systems',
  'https://www.bseindia.com/xml-data/corpfiling/AttachLive/demo-500103-fgd.pdf',
  'BSE Filing',
  'Bharat Heavy Electricals Limited has secured a contract valued at INR 1240 Crore from NTPC Limited for supply and installation of Flue Gas Desulphurisation systems across two thermal units. The order is to be executed over a period of 28 months from the date of the letter of award.',
  0.94, 'gpt-4o',
  'DEMO-NEWSID-500103-20260706', 'DEMO-NEWSID-500103-20260706', '2026-07-06T14:32:00Z'
),
-- 2) Bajel Projects (client example) — Power Transmission & Distribution
(
  'Bajel Projects Limited', '544204', 'BAJEL', 'INE0Z8Y01011',
  'INR 605.50 Crore', 605.5, 'Power Grid Corporation of India Limited', '18.0 Months', 18.0,
  'Power - Transmission & Distribution',
  'Engineering, procurement and construction of 765 kV transmission lines and associated substations.',
  'BSE', 'Award of Order / Receipt of Order',
  'Bajel Projects receives Rs 605.5 crore EPC order from Power Grid for 765 kV transmission lines',
  'https://www.bseindia.com/xml-data/corpfiling/AttachLive/demo-544204-765kv.pdf',
  'BSE Filing',
  'Bajel Projects Limited has received a Letter of Award from Power Grid Corporation of India Limited for an EPC contract worth INR 605.5 Crore covering 765 kV transmission lines and associated substations, to be completed within 18 months.',
  0.90, 'gpt-4o',
  'DEMO-NEWSID-544204-20260705', 'DEMO-NEWSID-544204-20260705', '2026-07-05T11:05:00Z'
),
-- 3) Ircon International — Infrastructure / Railways
(
  'Ircon International Limited', '541956', 'IRCON', 'INE962Y01021',
  'INR 2,310.00 Crore', 2310.0, 'Central Railway', '30.0 Months', 30.0,
  'Infrastructure - Railways',
  'Doubling of railway track including major bridges, electrification and signalling on a busy corridor.',
  'BSE', 'Award of Order / Receipt of Order',
  'Ircon International wins Rs 2,310 crore railway doubling and electrification order',
  'https://www.bseindia.com/xml-data/corpfiling/AttachLive/demo-541956-doubling.pdf',
  'BSE Filing',
  'Ircon International Limited has been awarded a contract valued at INR 2310 Crore by Central Railway for doubling of railway track, including construction of major bridges, electrification and signalling works. The project completion period is 30 months.',
  0.88, 'gpt-4o',
  'DEMO-NEWSID-541956-20260703', 'DEMO-NEWSID-541956-20260703', '2026-07-03T09:48:00Z'
),
-- 4) KEC International — value NOT specified, no announcement id (sha1 dedup path)
(
  'KEC International Limited', '532714', 'KEC', 'INE389H01022',
  'not specified', NULL, 'Undisclosed private developer', '24.0 Months', 24.0,
  'Power - Transmission & Distribution',
  'Supply of transmission towers and cabling for a renewable energy evacuation project; order value not disclosed.',
  'BSE', 'Award of Order / Receipt of Order',
  'KEC International secures new T&D order; value undisclosed',
  'https://www.bseindia.com/xml-data/corpfiling/AttachLive/demo-532714-td.pdf',
  'BSE Filing',
  'KEC International Limited has secured a new order in its Transmission and Distribution business for the supply of transmission towers and cabling for a renewable energy evacuation project. The value of the order was not disclosed in the filing. Execution period is 24 months.',
  0.72, 'gpt-4o',
  NULL, 'bd08436f7eaf2eab634ae1c37362601d1ae8ffed', '2026-07-01T16:20:00Z'
),
-- 5) Cochin Shipyard — Defence / Shipbuilding
(
  'Cochin Shipyard Limited', '540678', 'COCHINSHIP', 'INE704P01025',
  'INR 488.00 Crore', 488.0, 'Indian Navy', '40.0 Months', 40.0,
  'Defence - Shipbuilding',
  'Construction and delivery of two hydrographic survey vessels for the Indian Navy.',
  'BSE', 'Award of Order / Receipt of Order',
  'Cochin Shipyard bags Rs 488 crore Indian Navy order for survey vessels',
  'https://www.bseindia.com/xml-data/corpfiling/AttachLive/demo-540678-vessels.pdf',
  'BSE Filing',
  'Cochin Shipyard Limited has received an order valued at INR 488 Crore from the Indian Navy for the construction and delivery of two hydrographic survey vessels, to be delivered over a period of 40 months.',
  0.91, 'gpt-4o',
  'DEMO-NEWSID-540678-20260629', 'DEMO-NEWSID-540678-20260629', '2026-06-29T10:15:00Z'
);
