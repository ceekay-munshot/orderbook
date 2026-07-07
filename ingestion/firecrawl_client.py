"""Firecrawl client — proxied fetch fallback.

Used as a fallback when Scrape.do can't get past BSE's anti-bot (BSE blocks
datacenter IPs). Firecrawl's `/scrape` endpoint fetches a URL through its own
proxies (including residential/stealth) and returns the response body, which for
BSE's JSON API is the raw JSON we then parse.

We call the REST API directly with `requests` (no extra SDK dependency).
Docs: https://docs.firecrawl.dev/
"""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from config import Config

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"


class FirecrawlError(RuntimeError):
    """Raised when a Firecrawl request fails."""


def _find_marker_string(obj: Any) -> str | None:
    """Recursively find a string that looks like a BSE API body."""
    if isinstance(obj, str):
        s = obj.strip()
        if '"Table"' in obj or s in ('"No Record Found!"', "No Record Found!"):
            return obj
        return None
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_marker_string(v)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_marker_string(v)
            if found is not None:
                return found
    return None


def _extract_js_return(body: dict) -> tuple[str | None, str]:
    """Pull the executeJavascript return (the fetched API body) out of a Firecrawl
    response. Returns (value, debug_note)."""
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return None, f"no data dict (top keys={list(body) if isinstance(body, dict) else type(body).__name__})"

    candidates: list[Any] = []
    actions = data.get("actions")
    for container in (actions if isinstance(actions, dict) else {}, data):
        jsr = container.get("javascriptReturns") if isinstance(container, dict) else None
        if isinstance(jsr, list):
            for item in jsr:
                candidates.append(item.get("value") if isinstance(item, dict) else item)
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c, "javascriptReturns"

    found = _find_marker_string(body)
    if found is not None:
        return found, "recursive"

    dbg = f"data keys={list(data)}"
    if isinstance(actions, dict):
        dbg += f", actions keys={list(actions)}"
    else:
        dbg += f", actions={type(actions).__name__}"
    return None, dbg


class FirecrawlClient:
    """Fetch URLs through Firecrawl's scrape API."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 150.0,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._session = session or requests.Session()

    @classmethod
    def from_config(cls, config: Config) -> "FirecrawlClient":
        return cls(api_key=config.firecrawl_api_key or "")

    def scrape(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        proxy: str = "auto",
        retries: int = 0,
        backoff: float = 2.0,
        timeout: float | None = None,
    ) -> str:
        """Fetch ``url`` via Firecrawl and return the raw response body.

        ``headers`` are forwarded to the target (e.g. Referer + application/json
        so BSE returns its API JSON rather than the website HTML). ``proxy='auto'``
        lets Firecrawl escalate to stealth/residential proxies if a basic fetch
        is blocked. Returns the first non-empty of the rawHtml / html / markdown
        fields. Raises :class:`FirecrawlError`.
        """
        if not self._api_key:
            raise FirecrawlError("no Firecrawl API key configured")

        client_timeout = float(timeout or self._timeout)
        payload: dict[str, object] = {
            "url": url,
            "formats": ["rawHtml"],
            "onlyMainContent": False,
            "proxy": proxy,
            # Server-side budget for Firecrawl to solve BSE's bot check (stealth),
            # kept just under our client read timeout.
            "timeout": int(max(client_timeout - 15.0, 30.0) * 1000),
        }
        if headers:
            payload["headers"] = headers
        auth_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self._session.post(
                    FIRECRAWL_SCRAPE_URL,
                    json=payload,
                    headers=auth_headers,
                    timeout=client_timeout,
                )
            except requests.RequestException as exc:
                last_err = exc
            else:
                if resp.status_code == 200:
                    body = resp.json()
                    if not body.get("success", False):
                        raise FirecrawlError(f"Firecrawl error: {str(body)[:200]}")
                    data = body.get("data") or {}
                    for key in ("rawHtml", "html", "markdown", "content"):
                        value = data.get(key)
                        if value:
                            return value
                    return ""
                last_err = FirecrawlError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
                if resp.status_code not in (429, 500, 502, 503, 504):
                    raise last_err
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
        raise FirecrawlError(
            f"Firecrawl request failed after {retries + 1} attempt(s): {last_err}"
        )

    def fetch_json_via_browser(
        self,
        base_url: str,
        target_url: str,
        *,
        proxy: str = "auto",
        timeout: float | None = None,
    ) -> str:
        """Load ``base_url`` in Firecrawl's browser, then fetch ``target_url`` from
        inside that page's JavaScript (a same-context XHR, like the site's own SPA).

        This avoids forwarding browser-forbidden headers (Referer/User-Agent) —
        the real page context supplies the correct Origin/Referer + cookies, so
        BSE's API returns JSON instead of a webpage or a 400. Returns the fetched
        body (raw JSON text), or "" if nothing usable came back.
        """
        if not self._api_key:
            raise FirecrawlError("no Firecrawl API key configured")

        client_timeout = float(timeout or self._timeout)
        # No top-level await: Firecrawl runs the script as a plain (non-async)
        # function body, so wrap the async work in an IIFE and return its promise
        # (Playwright awaits a returned promise).
        script = (
            "return (async () => { const r = await fetch(" + json.dumps(target_url)
            + ", {headers: {'Accept': 'application/json, text/plain, */*'}, "
            "credentials: 'include'}); return await r.text(); })();"
        )
        payload: dict[str, object] = {
            "url": base_url,
            "formats": ["rawHtml"],
            "onlyMainContent": False,
            "proxy": proxy,
            "waitFor": 2500,
            "timeout": int(max(client_timeout - 15.0, 30.0) * 1000),
            "actions": [
                {"type": "wait", "milliseconds": 2000},
                {"type": "executeJavascript", "script": script},
            ],
        }
        auth_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = self._session.post(
                FIRECRAWL_SCRAPE_URL,
                json=payload,
                headers=auth_headers,
                timeout=client_timeout,
            )
        except requests.RequestException as exc:
            raise FirecrawlError(f"request failed: {exc}") from exc
        if resp.status_code != 200:
            raise FirecrawlError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        if not body.get("success", False):
            raise FirecrawlError(f"Firecrawl error: {str(body)[:300]}")

        value, debug = _extract_js_return(body)
        if value is None:
            print(f"    [firecrawl] in-page fetch returned nothing usable ({debug})")
            return ""
        return value
