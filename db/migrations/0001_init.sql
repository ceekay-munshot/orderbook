-- 0001_init.sql — PLACEHOLDER migration.
--
-- This is a stub so the migrations folder and D1 wiring exist. The REAL
-- orderbook schema (proper columns, types, indexes, per-company history,
-- source/evidence tracking, etc.) is defined in the next step (Step 2:
-- database schema) and will supersede this table.
--
-- Apply locally with:  wrangler d1 execute orderbook --local --file=./db/migrations/0001_init.sql
-- Apply remotely with: wrangler d1 execute orderbook --remote --file=./db/migrations/0001_init.sql

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company         TEXT,
    value           TEXT,
    awarder         TEXT,
    duration        TEXT,
    target_industry TEXT,
    description     TEXT,
    source_url      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
