"""Cloudflare D1 HTTP client.

The Python ingestion pipeline writes order rows into Cloudflare D1 through D1's
REST API (the web dashboard reads the same database via a Worker binding).

D1 query endpoint:
    POST https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query

Auth: Bearer token (a Cloudflare API token with D1 edit permission).
Body: {"sql": "...", "params": [...]}
"""

from __future__ import annotations

from typing import Any, Sequence

import requests

from config import Config

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


class D1Error(RuntimeError):
    """Raised when the D1 API returns an error or a non-2xx response."""


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
