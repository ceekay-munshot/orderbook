"""Entrypoint for the orderbook ingestion pipeline.

Two phases, run back to back:

  Phase 1 — FETCH: pull the latest order-win announcements from BSE for a date
  range, filter to order filings, dedup, take the order value straight from the
  summary line when it's stated there, and write new rows into the `orders`
  table. (Steps 4-5 fill the industry mapping.)

  Phase 2 — ENRICH: for orders ALREADY in the database that are still missing a
  value or a duration, read the filing's PDF (via Firecrawl, which downloads and
  parses it server-side), ask OpenAI to pull ONLY the missing fields out of the
  PDF text, normalize them to crore / months in code, and update the row. Each
  order is marked `pdf_checked` after one attempt (success or fail) so repeat
  runs don't re-download the same PDFs.

Runs in GitHub Actions. If the Cloudflare D1 secrets aren't set it runs Phase 1
in DRY-RUN mode (logs what it would write) and skips Phase 2 (which needs the DB).

Env:
  CF_ACCOUNT_ID / CF_D1_DATABASE_ID / CF_API_TOKEN -> write to remote D1 (all
                                              required; else DRY-RUN, no enrich)
  FIRECRAWL_API_KEY                         -> download + parse order PDFs
  OPENAI_API_KEY / OPENAI_MODEL             -> extract fields from PDF text
  INGEST_DAYS (default 2)                   -> fetch window = today-INGEST_DAYS..today
  INGEST_FROM_DATE / INGEST_TO_DATE (YYYY-MM-DD, optional) -> explicit overrides
  INGEST_LIMIT (default 10)                 -> max PDFs to enrich per run (cost cap)
  INGEST_MAX_PAGES (default 60)             -> cap on BSE page fetches per run
  FORCE_MASTER_REBUILD (default off)        -> rebuild the BSE<->NSE<->ISIN
                                              security master now (else weekly)

There is also a phase-0 build of the `security_master` translator (BSE scrip
code <-> NSE symbol <-> ISIN), the prerequisite for industry tagging. It is
cached and rebuilt at most weekly, so it is usually a no-op.
"""

from __future__ import annotations

import datetime
import glob
import os

from bse_client import (
    BSEReader,
    build_fetchers,
    duration_to_months,
    iter_matched,
    value_phrase_to_crore,
)
from config import Config
from d1_client import D1Client, compute_dedup_key
from firecrawl_client import FirecrawlClient, FirecrawlError
from openai_client import OpenAIClient, OpenAIError
from security_master import SecurityMasterError, build_master, verify

# BSE serves each PDF at AttachLive first; older ones move to AttachHis. We fall
# back to the historical path by swapping the folder in the stored URL.
_ATTACH_LIVE = "AttachLive"
_ATTACH_HIS = "AttachHis"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _bool_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _within_days(timestamp: str | None, days: int) -> bool:
    """True if `timestamp` (D1 'YYYY-MM-DD HH:MM:SS', UTC) is within `days` of now."""
    if not timestamp:
        return False
    try:
        when = datetime.datetime.fromisoformat(str(timestamp).replace(" ", "T"))
    except ValueError:
        return False
    return (datetime.datetime.utcnow() - when) < datetime.timedelta(days=days)


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


def ensure_schema(client: D1Client) -> None:
    """Apply every db/migrations/*.sql idempotently, so the workflow sets up and
    upgrades the database itself — no manual migration step needed.

    Migrations are applied in filename order. Re-running an ALTER/CREATE that has
    already been applied raises "duplicate column" / "already exists"; those are
    expected and ignored so the pass is safe to run on every workflow run.
    """
    pattern = os.path.join(
        os.path.dirname(__file__), "..", "db", "migrations", "*.sql"
    )
    paths = sorted(glob.glob(pattern))
    if not paths:
        print("  schema: no migration files found; assuming tables exist")
        return
    applied = already = 0
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"  schema: could not read {os.path.basename(path)} ({exc})")
            continue
        body = "\n".join(
            ln for ln in raw.splitlines() if not ln.lstrip().startswith("--")
        )
        for stmt in (s.strip() for s in body.split(";") if s.strip()):
            try:
                client.query(stmt)
                applied += 1
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                if "duplicate column" in msg or "already exists" in msg:
                    already += 1
                else:
                    print(f"  schema stmt skipped ({exc})")
                    already += 1
    tail = f", {already} already applied" if already else ""
    print(f"  schema: applied {applied} statement(s) across {len(paths)} migration(s){tail}")


def _fmt(order: dict) -> str:
    val = order.get("order_value_text") or "value→PDF"
    headline = (order.get("headline") or "")[:64]
    return f"{order['company_name']} | {val} | {order.get('filed_at')} | {headline}"


# --- phase 1: fetch new BSE orders -> text-extract -> write ------------------

def fetch_and_write(
    config: Config,
    client: D1Client | None,
    from_date: datetime.date,
    to_date: datetime.date,
) -> None:
    """Fetch order announcements for the date range and write new ones to D1.

    Order value is taken from the summary line when it states one; the remaining
    blanks are filled later by the PDF-enrichment pass. Never raises — a fetch
    failure logs and returns so Phase 2 still runs.
    """
    writing = client is not None
    fetchers = build_fetchers(config)
    print(f"\nfetch chain: {', '.join(name for name, _ in fetchers)}")
    print("(direct is primary + free; Scrape.do / Firecrawl are fallbacks)")

    max_pages = _int_env("INGEST_MAX_PAGES", 60)
    reader = BSEReader(fetchers, max_pages=max_pages)
    try:
        announcements = reader.fetch_range(from_date, to_date)
    except Exception as exc:  # noqa: BLE001 - never crash the workflow on fetch
        print(f"\nERROR: fetch failed: {type(exc).__name__}: {exc}")
        announcements = []

    if not announcements:
        print(
            "\nFetched 0 order announcements for this range — likely a non-trading "
            "day (or nothing new). No rows to write; enrichment still runs below."
        )
        return

    print(f"\nfetched    : {len(announcements)} announcements via {reader.source}")

    # filter + parse
    matched: list[dict] = []
    subcat_n = keyword_n = 0
    for order, rule, _detail in iter_matched(announcements):
        order["dedup_key"] = compute_dedup_key(order)
        matched.append(order)
        if rule == "subcat":
            subcat_n += 1
        else:
            keyword_n += 1
    print(f"order-match: {len(matched)} (subcat {subcat_n} / keyword {keyword_n})")

    # dedup within this batch
    seen: set[str] = set()
    deduped: list[dict] = []
    for order in matched:
        key = order["dedup_key"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(order)

    # dedup against the DB (write mode) so we don't re-insert saved filings
    if writing and client is not None:
        try:
            existing = client.existing_dedup_keys([o["dedup_key"] for o in deduped])
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: could not query existing dedup keys ({exc}); "
                  "relying on ON CONFLICT to dedup.")
            existing = set()
        new_items = [o for o in deduped if o["dedup_key"] not in existing]
        already = len(deduped) - len(new_items)
        print(f"WRITE mode : {len(new_items)} new "
              f"({already} already in D1) -> writing to remote D1")
    else:
        new_items = deduped
        print(f"DRY-RUN    : {len(new_items)} new (D1 secrets not set — not writing)")

    # write / log
    wrote = 0
    for order in new_items:
        if writing and client is not None:
            try:
                client.upsert_order(order)
                wrote += 1
                print("  wrote       " + _fmt(order))
            except Exception as exc:  # noqa: BLE001
                print(f"  FAILED ({exc}) " + _fmt(order))
        else:
            print("  would-write " + _fmt(order))

    with_value = sum(1 for o in new_items if o.get("order_value_text"))
    verb, count = ("wrote", wrote) if writing else ("would-write", len(new_items))
    print(
        f"\nphase 1 summary: {len(announcements)} fetched, {len(new_items)} new, "
        f"value-from-summary {with_value} ({len(new_items) - with_value} need PDF), "
        f"{verb} {count}"
    )


# --- phase 2: PDF-enrich existing DB rows still missing fields ---------------

def _his_fallback_url(url: str | None) -> str | None:
    """The AttachHis URL for a stored AttachLive URL (BSE moves older PDFs there)."""
    if url and _ATTACH_LIVE in url:
        return url.replace(_ATTACH_LIVE, _ATTACH_HIS)
    return None


def fetch_pdf_text(
    firecrawl: FirecrawlClient, order: dict
) -> tuple[str, str]:
    """Fetch + parse the order's PDF. Tries AttachLive, then AttachHis if that
    yields nothing (covers a 404 or an empty parse). Returns (text, source_note);
    text is "" when no readable text came back. Never raises."""
    live = order.get("attachment_url")
    candidates: list[tuple[str, str]] = []
    if live:
        candidates.append((_ATTACH_LIVE, live))
    his = _his_fallback_url(live)
    if his:
        candidates.append((_ATTACH_HIS, his))
    if not candidates:
        return "", "no attachment_url"

    notes: list[str] = []
    for label, url in candidates:
        try:
            text = firecrawl.scrape_pdf(url)
        except FirecrawlError as exc:
            notes.append(f"{label}: {exc}")
            continue
        if text and text.strip():
            return text, label
        notes.append(f"{label}: no text")
    return "", "; ".join(notes) or "no text"


def enrich_one(
    order: dict, firecrawl: FirecrawlClient, openai_client: OpenAIClient
) -> tuple[dict, str]:
    """Read one order's PDF and return (fields_to_update, note).

    `fields` always includes ``pdf_checked=1`` (we tried, success or fail) and,
    on success, ``raw_text`` = the PDF text (evidence) plus whichever of the
    *missing* fields the PDF stated. Only fields that are currently blank are
    filled; a field already present (e.g. value from the summary) is left alone.
    Normalization to crore / months happens here, from the verbatim phrase.
    """
    fields: dict = {"pdf_checked": 1}

    need_value = order.get("order_value_crore") is None
    need_duration = order.get("duration_months") is None
    need_awarder = not (order.get("awarder") or "").strip()

    text, source = fetch_pdf_text(firecrawl, order)
    if not text:
        return fields, f"no PDF text ({source})"

    # store the PDF text as evidence (trimmed to keep the row light)
    fields["raw_text"] = text[:20000]

    try:
        extraction = openai_client.extract(text)
    except OpenAIError as exc:
        return fields, f"PDF {source}, OpenAI failed: {exc}"

    fields["extraction_model"] = extraction.model
    if extraction.confidence is not None:
        fields["extraction_confidence"] = extraction.confidence

    filled: list[str] = []
    if need_value and extraction.order_value:
        vtext, vcrore = value_phrase_to_crore(extraction.order_value)
        if vcrore is not None:
            fields["order_value_text"] = vtext or extraction.order_value
            fields["order_value_crore"] = vcrore
            filled.append(f"value={vcrore}cr")
        else:  # phrase stated but no parseable number+unit — keep the phrase
            fields["order_value_text"] = extraction.order_value
            filled.append(f"value~“{extraction.order_value[:30]}”")

    if need_duration and extraction.duration:
        dtext, dmonths = duration_to_months(extraction.duration)
        if dmonths is not None:
            fields["duration_text"] = dtext or extraction.duration
            fields["duration_months"] = dmonths
            filled.append(f"duration={dmonths}mo")
        else:
            fields["duration_text"] = extraction.duration
            filled.append(f"duration~“{extraction.duration[:30]}”")

    if need_awarder and extraction.awarder:
        fields["awarder"] = extraction.awarder
        filled.append(f"awarder=“{extraction.awarder[:40]}”")

    note = f"PDF {source} -> " + (", ".join(filled) if filled else "nothing new stated")
    return fields, note


def renormalize_pass(client: D1Client) -> None:
    """Re-parse value/duration numbers from phrases ALREADY stored in D1 — free,
    no API calls. Fills rows where a phrase was saved but couldn't be turned into
    a number at the time (e.g. before a parser improvement), and runs before the
    paid PDF pass so it can shrink the list of orders still needing a PDF.
    """
    try:
        rows = client.orders_with_unparsed_text()
    except Exception as exc:  # noqa: BLE001
        print(f"\n  re-normalize: could not query ({exc}); skipping.")
        return
    if not rows:
        return
    fixed_value = fixed_duration = 0
    for row in rows:
        fields: dict = {}
        if row.get("order_value_crore") is None and row.get("order_value_text"):
            _vt, vcrore = value_phrase_to_crore(row["order_value_text"])
            if vcrore is not None:
                fields["order_value_crore"] = vcrore
                fixed_value += 1
        if row.get("duration_months") is None and row.get("duration_text"):
            _dt, dmonths = duration_to_months(row["duration_text"])
            if dmonths is not None:
                fields["duration_months"] = dmonths
                fixed_duration += 1
        if fields:
            try:
                client.update_order(row["id"], fields)
            except Exception as exc:  # noqa: BLE001
                print(f"  re-normalize: update failed for id={row.get('id')} ({exc})")
    if fixed_value or fixed_duration:
        print(f"\nre-normalize: filled value {fixed_value}, duration "
              f"{fixed_duration} from stored text (no API calls)")


def enrich_pass(client: D1Client, config: Config, limit: int) -> None:
    """Phase 2: read PDFs for DB orders still missing a value or duration.

    Queries up to `limit` such orders (cost guard), reads each PDF, extracts only
    the missing fields, updates the row and marks it pdf_checked. Never crashes
    the workflow — per-order failures are logged and the order is still marked
    checked so it isn't retried forever.
    """
    print("\n" + "=" * 40)
    print("phase 2: PDF enrichment")
    print("=" * 40)
    if not config.firecrawl_api_key:
        print("  FIRECRAWL_API_KEY not set — skipping PDF enrichment.")
        return
    if not config.openai_api_key:
        print("  OPENAI_API_KEY not set — skipping PDF enrichment.")
        return

    try:
        pending = client.orders_needing_pdf(limit)
    except Exception as exc:  # noqa: BLE001
        print(f"  could not query orders needing PDF ({exc}); skipping.")
        return

    print(f"  orders needing PDF: {len(pending)} (INGEST_LIMIT={limit})")
    if not pending:
        print("  nothing to enrich — all orders have value+duration or were checked.")
        return

    firecrawl = FirecrawlClient.from_config(config)
    openai_client = OpenAIClient.from_config(config)
    print(f"  using model: {openai_client.model}\n")

    n_value = n_duration = n_awarder = 0
    n_updated = n_no_text = n_errors = 0
    for order in pending:
        label = f"{order.get('company_name', '?')} (id={order.get('id')})"
        try:
            fields, note = enrich_one(order, firecrawl, openai_client)
        except Exception as exc:  # noqa: BLE001 - never crash the whole pass
            fields, note = {"pdf_checked": 1}, f"unexpected error: {exc}"
            n_errors += 1

        if "order_value_crore" in fields:
            n_value += 1
        if "duration_months" in fields:
            n_duration += 1
        if "awarder" in fields:
            n_awarder += 1
        if note.startswith("no PDF text"):
            n_no_text += 1

        try:
            client.update_order(order["id"], fields)
            n_updated += 1
            print(f"  ✓ {label}: {note}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {label}: update failed ({exc}) [{note}]")

    print(
        f"\nphase 2 summary: checked {n_updated}/{len(pending)} orders — filled "
        f"value {n_value}, duration {n_duration}, awarder {n_awarder}; "
        f"no-text PDFs {n_no_text}, errors {n_errors}"
    )


def build_security_master_pass(client: D1Client | None, config: Config) -> None:
    """Build the BSE<->NSE<->ISIN translator (security_master).

    Rebuilt AT MOST weekly (it changes rarely) — skipped if the table is fresh,
    unless FORCE_MASTER_REBUILD is set. In dry-run (no D1) it builds + logs but
    doesn't write. Never crashes the run; a fetch failure keeps the existing
    master. This is the prerequisite for industry tagging (next step).
    """
    print("\n" + "=" * 40)
    print("security master (BSE <-> NSE <-> ISIN)")
    print("=" * 40)

    force = _bool_env("FORCE_MASTER_REBUILD")
    if client is not None:
        try:
            n_existing, last = client.security_master_status()
        except Exception as exc:  # noqa: BLE001
            print(f"  status check failed ({exc}); will attempt a build.")
            n_existing, last = 0, None
        if n_existing > 0 and not force and _within_days(last, 7):
            print(f"  fresh: {n_existing} rows, updated {last} (<7d) — skipping "
                  "rebuild. Set FORCE_MASTER_REBUILD=1 to force.")
            return
        reason = "forced" if force else (
            f"stale (updated {last})" if n_existing else "empty")
        print(f"  rebuilding — {reason}")
    else:
        print("  DRY-RUN (no D1) — building + logging, not writing")

    try:
        rows, stats = build_master(config)
    except SecurityMasterError as exc:
        print(f"  FETCH FAILED: {exc}. Keeping any existing master.")
        return

    print(f"  sources: NSE {stats['nse_rows']} symbols (EQUITY_L.csv), "
          f"BSE {stats['bse_rows']} scrips (ListofScripData)")
    print(f"  joined on ISIN -> {stats['total']} rows "
          f"({stats['with_nse']} with NSE symbol, {stats['bse_only']} BSE-only)")

    all_ok = True
    for scrip, symbol, isin, row, ok in verify(rows):
        got = f"{row['nse_symbol']} / {row['isin']}" if row else "NOT FOUND"
        print(f"  verify {scrip}: {'OK  ' if ok else 'FAIL'} -> {got} "
              f"(expect {symbol} / {isin})")
        all_ok = all_ok and ok
    if not all_ok:
        print("  WARNING: a known mapping did not resolve — check the sources.")

    if client is None:
        print(f"  would upsert {len(rows)} rows into security_master (dry-run)")
        return
    try:
        wrote = client.upsert_security_master(rows)
        print(f"  upserted {wrote} rows into security_master")
    except Exception as exc:  # noqa: BLE001
        print(f"  WRITE FAILED ({exc}); master left unchanged.")


def main() -> int:
    config = Config.from_env()
    from_date, to_date = resolve_date_range()

    print("orderbook ingestion — fetch + PDF enrichment")
    print("=" * 40)
    print(f"date range : {from_date} -> {to_date}")

    writing = db_configured(config)
    client: D1Client | None = None
    if writing:
        client = D1Client.from_config(config)
        ensure_schema(client)  # create/upgrade tables (idempotent)
    else:
        print("D1 secrets not set -> DRY-RUN (no DB writes; PDF enrichment skipped)")

    # Company translator (BSE<->NSE<->ISIN) — prerequisite for industry tagging.
    # Cached weekly, so this is usually a no-op.
    build_security_master_pass(client, config)

    # Phase 1 — fetch new BSE orders and write them.
    fetch_and_write(config, client, from_date, to_date)

    # Phase 2 — enrich existing DB rows that still need value/duration.
    if writing and client is not None:
        renormalize_pass(client)  # free: recover numbers from stored phrases
        enrich_pass(client, config, _int_env("INGEST_LIMIT", 10))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
