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
from typing import Any, Sequence

import requests

from config import Config

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


class D1Error(RuntimeError):
    """Raised when the D1 API returns an error or a non-2xx response."""


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
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        if not (account_id and database_id and api_token):
            raise ValueError(
                "account_id, database_id and api_token are all required"
            )
        self._account_id = account_id
        self._database_id = database_id
        self._timeout = timeout
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
        self, sql: str, params: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a single SQL statement and return its result rows.

        Args:
            sql: A single SQL statement, using ``?`` placeholders for params.
            params: Values to bind to the placeholders, in order.

        Returns:
            The list of row dicts from the first result set (empty for
            statements that don't return rows, e.g. INSERT/UPDATE).

        Raises:
            D1Error: If the request fails or D1 reports ``success: false``.
        """
        payload: dict[str, Any] = {"sql": sql}
        if params is not None:
            payload["params"] = list(params)

        try:
            resp = self._session.post(
                self._query_url, json=payload, timeout=self._timeout
            )
        except requests.RequestException as exc:  # network-level failure
            raise D1Error(f"D1 request failed: {exc}") from exc

        try:
            body = resp.json()
        except ValueError as exc:
            raise D1Error(
                f"D1 returned non-JSON response (HTTP {resp.status_code})"
            ) from exc

        if not resp.ok or not body.get("success", False):
            errors = body.get("errors") or [{"message": resp.text}]
            raise D1Error(f"D1 API error (HTTP {resp.status_code}): {errors}")

        # `result` is a list of statement results; return rows from the first.
        result = body.get("result") or []
        if not result:
            return []
        return result[0].get("results", []) or []

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
