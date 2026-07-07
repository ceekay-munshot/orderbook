"""Entrypoint for the orderbook ingestion pipeline — Step 3: the BSE reader.

Fetches real order announcements from BSE for a date range, filters to
order-related filings, dedups, and writes the announcement metadata into the
`orders` table (the 5 extracted fields stay NULL — Steps 4-5 fill them). Runs in
GitHub Actions. If the Cloudflare D1 secrets aren't set it runs in DRY-RUN mode
(logs what it would write) instead of crashing.

Env:
  SCRAPEDO_API_KEY                         -> fetch through the Scrape.do proxy
  CF_ACCOUNT_ID / CF_D1_DATABASE_ID / CF_API_TOKEN -> write to remote D1 (all
                                              required to write; else DRY-RUN)
  INGEST_DAYS (default 2)                   -> fetch window = today-INGEST_DAYS..today
  INGEST_FROM_DATE / INGEST_TO_DATE (YYYY-MM-DD, optional) -> explicit overrides
"""

from __future__ import annotations

import datetime
import os

from bse_client import BSEReader, build_fetchers, iter_matched
from config import Config
from d1_client import D1Client, compute_dedup_key


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def resolve_date_range() -> tuple[datetime.date, datetime.date]:
    """Resolve [from_date, to_date] from INGEST_* env vars."""
    today = datetime.date.today()
    to_raw = os.getenv("INGEST_TO_DATE")
    from_raw = os.getenv("INGEST_FROM_DATE")
    to_date = datetime.date.fromisoformat(to_raw) if to_raw else today
    if from_raw:
        from_date = datetime.date.fromisoformat(from_raw)
    else:
        from_date = to_date - datetime.timedelta(days=_int_env("INGEST_DAYS", 2))
    return from_date, to_date


def db_configured(config: Config) -> bool:
    """True only when all three Cloudflare D1 credentials are present."""
    return all(
        bool(v)
        for v in (config.cf_account_id, config.cf_d1_database_id, config.cf_api_token)
    )


def _fmt(order: dict, rule: str, detail: str | None) -> str:
    tag = f"{rule}:{detail}" if detail else rule
    headline = (order.get("headline") or "")[:80]
    return (
        f"[{tag}] {order['company_name']} | {order.get('filed_at')} | "
        f"{headline} | {order.get('attachment_url')}"
    )


def main() -> int:
    config = Config.from_env()
    from_date, to_date = resolve_date_range()

    print("orderbook BSE reader")
    print("=" * 40)
    print(f"date range : {from_date} -> {to_date}")

    # --- fetch ---------------------------------------------------------------
    fetchers = build_fetchers(config)
    print(f"fetch chain: {', '.join(name for name, _ in fetchers)}")
    print("(BSE blocks datacenter IPs; Scrape.do uses residential 'super', "
          "Firecrawl uses stealth proxies)\n")

    # Firecrawl stealth solves BSE's bot check per page (~1-2 min each), so cap
    # pages to bound run time/credits. Raise INGEST_MAX_PAGES once it's writing.
    max_pages = _int_env("INGEST_MAX_PAGES", 10)
    reader = BSEReader(fetchers, max_pages=max_pages)
    try:
        announcements = reader.fetch_range(from_date, to_date)
    except Exception as exc:  # noqa: BLE001 - never crash the workflow on fetch
        print(f"\nERROR: fetch failed: {type(exc).__name__}: {exc}")
        print("Could not fetch announcements from BSE. Exiting without changes.")
        return 0

    if not announcements:
        print("\nFetched 0 announcements — every fetcher returned no data (see the "
              "per-fetcher samples above).")
        print("If a sample is \"No Record Found!\" the proxy IP was blocked by BSE "
              "(needs residential proxies); otherwise there were no filings in range.")
        print("Nothing to do.")
        return 0

    print(f"\nfetched    : {len(announcements)} announcements via {reader.source}")

    # --- filter + parse ------------------------------------------------------
    matched: list[tuple[dict, str, str | None]] = []
    subcat_n = keyword_n = 0
    for order, rule, detail in iter_matched(announcements):
        order["dedup_key"] = compute_dedup_key(order)
        matched.append((order, rule, detail))
        if rule == "subcat":
            subcat_n += 1
        else:
            keyword_n += 1
    print(f"order-match: {len(matched)} (subcat {subcat_n} / keyword {keyword_n})")

    # dedup within this batch (keep first occurrence of each dedup_key)
    seen: set[str] = set()
    deduped: list[tuple[dict, str, str | None]] = []
    for order, rule, detail in matched:
        key = order["dedup_key"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append((order, rule, detail))

    # --- decide write vs dry-run + dedup against DB --------------------------
    writing = db_configured(config)
    client: D1Client | None = None
    if writing:
        client = D1Client.from_config(config)
        try:
            existing = client.existing_dedup_keys([o["dedup_key"] for o, _, _ in deduped])
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: could not query existing dedup keys ({exc}); "
                  "relying on ON CONFLICT to dedup.")
            existing = set()
        new_items = [t for t in deduped if t[0]["dedup_key"] not in existing]
        already = len(deduped) - len(new_items)
        print(f"\nWRITE mode : {len(new_items)} new "
              f"({already} already in D1) -> writing to remote D1")
    else:
        new_items = deduped
        print(f"\nDRY-RUN    : {len(new_items)} new (D1 secrets not set — not writing; "
              "can't dedup against DB)")

    # --- write / log ---------------------------------------------------------
    wrote = 0
    for order, rule, detail in new_items:
        if writing and client is not None:
            try:
                client.upsert_order(order)
                wrote += 1
                print("  wrote       " + _fmt(order, rule, detail))
            except Exception as exc:  # noqa: BLE001
                print(f"  FAILED ({exc}) " + _fmt(order, rule, detail))
        else:
            print("  would-write " + _fmt(order, rule, detail))

    # --- summary -------------------------------------------------------------
    verb, count = ("wrote", wrote) if writing else ("would-write", len(new_items))
    print(
        f"\nsummary: fetched {len(announcements)}, "
        f"order-matched {len(matched)} (subcat {subcat_n} / keyword {keyword_n}), "
        f"new {len(new_items)}, {verb} {count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
