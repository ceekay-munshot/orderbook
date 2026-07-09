"""Standalone industry-classification refresh (its own GitHub workflow).

Split out of the main ingest (`main.py`) because rebuilding the industry map is
the slow part of the pipeline — the full stockscans.in pull (~5,800 companies)
plus the BSE fallback for the tail is thousands of HTTP calls and can take many
minutes. It also changes slowly, so it doesn't need to run every few hours with
the order fetch.

So the work is split:
  * main.py (every few hours)  — fetch orders, enrich PDFs, and TAG orders from
                                 the cached industry_map (cheap).
  * this job (own schedule)    — (re)build the security_master translator and the
                                 industry_map (stockscans + BSE), then re-tag all
                                 orders from the fresh map.

Both honor their caches (security_master weekly, industry_map ~3 days), so a run
where nothing is stale is a cheap no-op. FORCE_MASTER_REBUILD / FORCE_INDUSTRY_
REFRESH force a rebuild now. Needs the Cloudflare D1 secrets; without them there
is nothing to refresh, so it exits cleanly.
"""

from __future__ import annotations

from config import Config
from d1_client import D1Client
from main import (
    build_security_master_pass,
    db_configured,
    ensure_schema,
    tag_orders_pass,
)


def main() -> int:
    config = Config.from_env()

    print("orderbook — industry classification refresh")
    print("=" * 40)

    if not db_configured(config):
        print("D1 secrets not set -> nothing to refresh (this job needs the DB). "
              "Exiting cleanly.")
        return 0

    client = D1Client.from_config(config)
    ensure_schema(client)  # create/upgrade tables (idempotent)

    # Prerequisite for industry tagging: the BSE<->NSE<->ISIN translator. Cached
    # weekly, so usually a no-op (FORCE_MASTER_REBUILD to force).
    build_security_master_pass(client, config)

    # Rebuild industry_map (stockscans + BSE fallback) and re-tag every order.
    tag_orders_pass(client, config)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
