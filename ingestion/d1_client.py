"""Cloudflare D1 HTTP client.

The Python ingestion pipeline writes order rows into Cloudflare D1 through D1's
REST API (the web dashboard reads the same database via a Worker binding).

D1 query endpoint:
    POST https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query

Auth: Bearer token (a Cloudflare API token with D1 edit permission).
Body: {"sql": "...", "params": [...]}
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Sequence

import requests

from config import Config

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"

# HTTP statuses worth retrying — transient Cloudflare-side hiccups, not our bug.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class D1Error(RuntimeError):
    """Raised when the D1 API returns an error or a non-2xx response."""


def _sql_literal(value: Any) -> str:
    """Render a value as a safe SQLite string literal (or NULL).

    Single quotes are doubled per the SQL standard (SQLite has no backslash
    escapes), and control characters are dropped. Used for bulk inserts where
    inlining beats thousands of parameterized round-trips.
    """
    if value is None:
        return "NULL"
    text = str(value).replace("'", "''")
    text = "".join(ch for ch in text if ch >= " " or ch == "\t")
    return "'" + text + "'"


# Columns written by upsert_order(), in bind order. Excludes auto-managed
# columns: id, created_at, updated_at.
ORDER_COLUMNS: tuple[str, ...] = (
    "company_name",
    "bse_scrip_code",
    "nse_symbol",
    "isin",
    "order_value_text",
    "order_value_crore",
    "awarder",
    "duration_text",
    "duration_months",
    "target_industry",
    "description",
    "exchange",
    "category",
    "headline",
    "attachment_url",
    "source_label",
    "raw_text",
    "extraction_confidence",
    "extraction_model",
    "bse_announcement_id",
    "dedup_key",
    "filed_at",
)

# Columns the PDF-enrichment step is allowed to UPDATE in place. An allowlist so
# a typo in a field name fails loudly instead of building malformed SQL.
UPDATABLE_COLUMNS: frozenset[str] = frozenset(
    {
        "order_value_text",
        "order_value_crore",
        "awarder",
        "duration_text",
        "duration_months",
        "target_industry",
        "description",
        "raw_text",
        "extraction_confidence",
        "extraction_model",
        "pdf_checked",
    }
)


def compute_dedup_key(order: dict[str, Any]) -> str:
    """Return a stable dedup key so we never double-insert the same filing.

    Prefers the BSE announcement id (NEWSID) when present; otherwise falls back
    to a sha1 hash of "scrip|filed_at|headline". Mirrors the strategy used in
    db/seed.sql.
    """
    announcement_id = order.get("bse_announcement_id")
    if announcement_id:
        return str(announcement_id)
    scrip = order.get("bse_scrip_code") or ""
    filed_at = order.get("filed_at") or ""
    headline = order.get("headline") or ""
    basis = f"{scrip}|{filed_at}|{headline}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


class D1Client:
    """Minimal client for running SQL against a Cloudflare D1 database."""

    def __init__(
        self,
        account_id: str,
        database_id: str,
        api_token: str,
        *,
        timeout: float = 45.0,
        retries: int = 3,
        backoff: float = 1.5,
        session: requests.Session | None = None,
    ) -> None:
        if not (account_id and database_id and api_token):
            raise ValueError(
                "account_id, database_id and api_token are all required"
            )
        self._account_id = account_id
        self._database_id = database_id
        self._timeout = timeout
        self._retries = max(0, retries)
        self._backoff = backoff
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def from_config(cls, config: Config, **kwargs: Any) -> "D1Client":
        """Construct a client from a :class:`~config.Config`."""
        return cls(
            account_id=config.cf_account_id or "",
            database_id=config.cf_d1_database_id or "",
            api_token=config.cf_api_token or "",
            **kwargs,
        )

    @property
    def _query_url(self) -> str:
        return (
            f"{CLOUDFLARE_API_BASE}/accounts/{self._account_id}"
            f"/d1/database/{self._database_id}/query"
        )

    def query(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
        *,
        idempotent: bool = True,
    ) -> list[dict[str, Any]]:
        """Run a single SQL statement and return its result rows.

        Args:
            sql: A single SQL statement, using ``?`` placeholders for params.
            params: Values to bind to the placeholders, in order.
            idempotent: When True (the default) a transient failure — a network
                timeout or a 5xx/429 from the Cloudflare API — is retried with
                backoff. Safe for SELECTs, DELETEs, UPDATEs, and ON-CONFLICT
                upserts (re-running them lands the same state). Pass False for a
                plain INSERT that must not be re-sent (a timed-out request may
                have committed server-side); the caller retries at a safe
                granularity instead (see :meth:`replace_industry_map`).

        Returns:
            The list of row dicts from the first result set (empty for
            statements that don't return rows, e.g. INSERT/UPDATE).

        Raises:
            D1Error: If the request fails or D1 reports ``success: false``.
        """
        payload: dict[str, Any] = {"sql": sql}
        if params is not None:
            payload["params"] = list(params)

        attempts = self._retries + 1 if idempotent else 1
        last: D1Error | None = None
        for attempt in range(attempts):
            retryable = False
            try:
                resp = self._session.post(
                    self._query_url, json=payload, timeout=self._timeout
                )
            except requests.RequestException as exc:  # network-level failure
                last = D1Error(f"D1 request failed: {exc}")
                retryable = True  # timeout / connection reset — worth another try
            else:
                try:
                    body = resp.json()
                except ValueError as exc:
                    last = D1Error(
                        f"D1 returned non-JSON response (HTTP {resp.status_code})"
                    )
                    retryable = resp.status_code in _RETRYABLE_STATUS
                else:
                    if resp.ok and body.get("success", False):
                        # `result` is a list of statement results; return the first.
                        result = body.get("result") or []
                        if not result:
                            return []
                        return result[0].get("results", []) or []
                    errors = body.get("errors") or [{"message": resp.text}]
                    last = D1Error(f"D1 API error (HTTP {resp.status_code}): {errors}")
                    retryable = resp.status_code in _RETRYABLE_STATUS

            if not retryable or attempt >= attempts - 1:
                break
            time.sleep(self._backoff * (2 ** attempt))
        raise last or D1Error("D1 request failed")

    def upsert_order(self, order: dict[str, Any]) -> list[dict[str, Any]]:
        """Insert an order, or update it in place if its dedup_key already exists.

        `order` is a dict keyed by the snake_case column names (see
        db/migrations/0001_init.sql). Missing keys are stored as NULL, except:
          - `exchange` defaults to 'BSE'
          - `dedup_key` is computed via compute_dedup_key() when absent
        `updated_at` is refreshed on every update. This is the write path that
        Steps 3-5 (BSE ingestion + extraction) will call.
        """
        row = dict(order)
        row["exchange"] = row.get("exchange") or "BSE"
        if not row.get("dedup_key"):
            row["dedup_key"] = compute_dedup_key(row)

        columns = ", ".join(ORDER_COLUMNS)
        placeholders = ", ".join("?" for _ in ORDER_COLUMNS)
        params = [row.get(col) for col in ORDER_COLUMNS]

        # On conflict, refresh every column except the conflict key, and bump
        # updated_at. created_at is preserved.
        updates = ", ".join(
            f"{col} = excluded.{col}"
            for col in ORDER_COLUMNS
            if col != "dedup_key"
        )
        sql = (
            f"INSERT INTO orders ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(dedup_key) DO UPDATE SET {updates}, "
            f"updated_at = datetime('now')"
        )
        return self.query(sql, params)

    def orders_needing_pdf(self, limit: int) -> list[dict[str, Any]]:
        """Return orders that still need PDF enrichment.

        A row qualifies when it is missing a value OR a duration (in the
        normalized crore/months columns) AND has not been PDF-checked yet. Newest
        first, capped at ``limit`` (the per-run cost guard). Rows that already
        have both value and duration are never returned — their PDF is skipped.
        """
        sql = (
            "SELECT id, dedup_key, company_name, attachment_url, headline, "
            "description, order_value_text, order_value_crore, duration_text, "
            "duration_months, awarder, raw_text "
            "FROM orders "
            "WHERE (order_value_crore IS NULL OR duration_months IS NULL) "
            "AND (pdf_checked IS NULL OR pdf_checked = 0) "
            "ORDER BY filed_at DESC LIMIT ?"
        )
        return self.query(sql, [int(limit)])

    def security_master_status(self) -> tuple[int, str | None]:
        """Return (row_count, max_updated_at) for security_master.

        Used to honor the weekly-rebuild cache — if the table is fresh we skip
        re-fetching the source lists. Returns (0, None) when empty/missing.
        """
        rows = self.query(
            "SELECT COUNT(*) AS n, MAX(updated_at) AS last FROM security_master"
        )
        if not rows:
            return 0, None
        return int(rows[0].get("n") or 0), rows[0].get("last")

    def security_master_bse_symbol_populated(self) -> bool:
        """True if any security_master row carries a BSE ticker (bse_symbol).

        Lets the build pass detect a freshly-added-but-empty column (right after
        the 0004 migration) and refill it once, even if the weekly cache is fresh.
        """
        rows = self.query(
            "SELECT COUNT(*) AS n FROM security_master WHERE bse_symbol IS NOT NULL"
        )
        return bool(rows and int(rows[0].get("n") or 0) > 0)

    def upsert_security_master(
        self,
        rows: Sequence[dict[str, Any]],
        *,
        batch: int = 400,
    ) -> int:
        """Bulk-upsert translator rows into security_master, keyed by scrip code.

        Values are inlined as escaped SQL literals (single quotes doubled) so a
        whole batch of rows goes in ONE statement — thousands of rows would be
        far too many round-trips one at a time. The data comes from BSE/NSE
        official lists, and every string is escaped, so this is injection-safe.
        Returns the number of rows written.
        """
        cols = (
            "(bse_scrip_code, isin, nse_symbol, bse_symbol, company_name, "
            "source, updated_at)"
        )
        written = 0
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]
            tuples = []
            for r in chunk:
                tuples.append(
                    "("
                    + ", ".join(
                        (
                            _sql_literal(r.get("bse_scrip_code")),
                            _sql_literal(r.get("isin")),
                            _sql_literal(r.get("nse_symbol")),
                            _sql_literal(r.get("bse_symbol")),
                            _sql_literal(r.get("company_name")),
                            _sql_literal(r.get("source")),
                            "datetime('now')",
                        )
                    )
                    + ")"
                )
            sql = (
                f"INSERT INTO security_master {cols} VALUES "
                + ", ".join(tuples)
                + " ON CONFLICT(bse_scrip_code) DO UPDATE SET "
                "isin = excluded.isin, nse_symbol = excluded.nse_symbol, "
                "bse_symbol = excluded.bse_symbol, "
                "company_name = excluded.company_name, source = excluded.source, "
                "updated_at = datetime('now')"
            )
            self.query(sql)
            written += len(chunk)
        return written

    def security_master_symbol_rows(self) -> list[dict[str, Any]]:
        """Return security_master rows that can carry an industry — i.e. have an
        NSE symbol OR a BSE ticker (so BSE-only companies are included too).
        Columns: scrip, isin, nse_symbol, bse_symbol, company_name."""
        return self.query(
            "SELECT bse_scrip_code, isin, nse_symbol, bse_symbol, company_name "
            "FROM security_master "
            "WHERE nse_symbol IS NOT NULL OR bse_symbol IS NOT NULL"
        )

    def industry_map_status(self) -> tuple[int, str | None, str | None]:
        """Return (row_count, max_updated_at, source) for industry_map — used to
        honor the multi-day cache of the full stockscans pull. Rows are stamped
        with their own source ('stockscans_full', 'bse', 'stockscans_daksham');
        MAX(source) returns 'stockscans_full' whenever the full pull ran (it
        sorts above 'bse'), which is exactly the "is the map fully built?" signal
        the caller caches on — a degraded daksham/BSE-only build sorts lower and
        so is (correctly) never treated as fresh."""
        rows = self.query(
            "SELECT COUNT(*) AS n, MAX(updated_at) AS last, MAX(source) AS source "
            "FROM industry_map"
        )
        if not rows:
            return 0, None, None
        return int(rows[0].get("n") or 0), rows[0].get("last"), rows[0].get("source")

    def industry_map_by_scrip(self) -> dict[str, str]:
        """Return {bse_scrip_code -> industry} from industry_map, for tagging
        orders straight from the cached map (no re-pull)."""
        rows = self.query(
            "SELECT bse_scrip_code, industry FROM industry_map "
            "WHERE bse_scrip_code IS NOT NULL AND industry IS NOT NULL"
        )
        return {r["bse_scrip_code"]: r["industry"] for r in rows if r.get("bse_scrip_code")}

    def all_orders_scrips(self) -> list[dict[str, Any]]:
        """Return (id, bse_scrip_code, company_name) for EVERY order — tagging
        re-runs over all orders so a changed mapping updates existing rows too."""
        return self.query("SELECT id, bse_scrip_code, company_name FROM orders")

    def replace_industry_map(
        self,
        rows: Sequence[dict[str, Any]],
        *,
        source: str = "stockscans_full",
        batch: int = 300,
        attempts: int = 3,
    ) -> int:
        """Rebuild industry_map from scratch (DELETE then batch INSERT).

        The table is derived from security_master × the industry sources
        (stockscans primary, BSE fallback), so a clean replace avoids stale rows
        when a mapping changes. Only rows that carry an industry are inserted
        (industry is NOT NULL). Each row's own ``source`` is stamped (falling
        back to the ``source`` arg), so a mixed build keeps per-company
        provenance; ``sub_industry`` and updated_at are written too.

        The map is now ~4,900 rows (BSE fallback ~tripled it), so the whole
        DELETE + batched-INSERT sequence is retried as ONE unit on a transient D1
        failure: each attempt re-DELETEs first, so a mid-write timeout can never
        leave a partial map or duplicate rows (the inserts are plain INSERTs, so
        they're sent with idempotent=False — no per-statement retry that could
        double-insert a batch whose response merely timed out).
        """
        cols = (
            "(bse_scrip_code, isin, nse_symbol, company_name, "
            "name_normalized, industry, sub_industry, source, updated_at)"
        )
        # Pre-render every statement once (DELETE first, then the INSERT batches).
        statements = ["DELETE FROM industry_map"]
        for i in range(0, len(rows), batch):
            tuples = []
            for r in rows[i : i + batch]:
                name = r.get("company_name")
                tuples.append(
                    "("
                    + ", ".join(
                        (
                            _sql_literal(r.get("bse_scrip_code")),
                            _sql_literal(r.get("isin")),
                            _sql_literal(r.get("nse_symbol")),
                            _sql_literal(name),
                            _sql_literal(name.lower() if name else None),
                            _sql_literal(r.get("industry")),
                            _sql_literal(r.get("sub_industry")),
                            _sql_literal(r.get("source") or source),
                            "datetime('now')",
                        )
                    )
                    + ")"
                )
            statements.append(f"INSERT INTO industry_map {cols} VALUES " + ", ".join(tuples))

        last: Exception | None = None
        for attempt in range(max(1, attempts)):
            try:
                for stmt in statements:  # DELETE clears any partial write first
                    self.query(stmt, idempotent=False)
                return len(rows)
            except D1Error as exc:
                last = exc
                if attempt < attempts - 1:
                    time.sleep(self._backoff * (2 ** attempt))
        raise last or D1Error("industry_map replace failed")

    def set_target_industry_bulk(self, id_to_industry: dict[Any, str]) -> int:
        """Set orders.target_industry for many orders efficiently.

        Groups order ids by their (identical) industry value and issues one
        UPDATE per distinct industry — a handful of statements instead of one
        per order. Ids are ints (coerced), industry is escaped, so it is safe.
        """
        groups: dict[str, list[int]] = {}
        for order_id, industry in id_to_industry.items():
            groups.setdefault(industry, []).append(int(order_id))
        updated = 0
        for industry, ids in groups.items():
            for i in range(0, len(ids), 500):
                chunk = ids[i : i + 500]
                id_list = ", ".join(str(x) for x in chunk)
                self.query(
                    f"UPDATE orders SET target_industry = {_sql_literal(industry)}, "
                    f"updated_at = datetime('now') WHERE id IN ({id_list})"
                )
                updated += len(chunk)
        return updated

    def orders_with_unparsed_text(self) -> list[dict[str, Any]]:
        """Return orders that have a value/duration *phrase* stored but no parsed
        number yet — candidates for a free re-normalize (no API calls).

        These are typically rows the enrichment step filled with a raw phrase it
        couldn't turn into a number at the time; an improved parser can retry
        them straight from the stored text.
        """
        sql = (
            "SELECT id, order_value_text, order_value_crore, duration_text, "
            "duration_months FROM orders "
            "WHERE (order_value_crore IS NULL AND order_value_text IS NOT NULL) "
            "OR (duration_months IS NULL AND duration_text IS NOT NULL)"
        )
        return self.query(sql)

    def update_order(
        self, row_id: Any, fields: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Update specific columns of one order row (by id) and bump updated_at.

        Only the columns present in ``fields`` are written; the rest are left as
        they are. Every key must be in :data:`UPDATABLE_COLUMNS`. Used by the
        PDF-enrichment step to fill blanks and mark ``pdf_checked``.
        """
        if not fields:
            return []
        bad = [k for k in fields if k not in UPDATABLE_COLUMNS]
        if bad:
            raise D1Error(f"update_order: columns not updatable: {bad}")
        columns = list(fields.keys())
        assignments = ", ".join(f"{col} = ?" for col in columns)
        params: list[Any] = [fields[col] for col in columns]
        params.append(row_id)
        sql = (
            f"UPDATE orders SET {assignments}, updated_at = datetime('now') "
            f"WHERE id = ?"
        )
        return self.query(sql, params)

    def existing_dedup_keys(self, keys: Sequence[str]) -> set[str]:
        """Return the subset of `keys` already present in the orders table.

        Used to skip announcements we've already ingested. Queries in chunks to
        keep each SQL statement small.
        """
        wanted = [k for k in keys if k]
        found: set[str] = set()
        chunk = 100
        for i in range(0, len(wanted), chunk):
            batch = wanted[i : i + chunk]
            placeholders = ", ".join("?" for _ in batch)
            rows = self.query(
                f"SELECT dedup_key FROM orders WHERE dedup_key IN ({placeholders})",
                batch,
            )
            for row in rows:
                key = row.get("dedup_key")
                if key:
                    found.add(key)
        return found
