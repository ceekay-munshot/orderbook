"""Firecrawl client — proxied fetch fallback.

Used as a fallback when Scrape.do can't get past BSE's anti-bot (BSE blocks
datacenter IPs). Firecrawl's `/scrape` endpoint fetches a URL through its own
proxies (including residential/stealth) and returns the response body, which for
BSE's JSON API is the raw JSON we then parse.

We call the REST API directly with `requests` (no extra SDK dependency).
Docs: https://docs.firecrawl.dev/
"""

from __future__ import annotations

import time

import requests

from config import Config

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"


class FirecrawlError(RuntimeError):
    """Raised when a Firecrawl request fails."""


class FirecrawlClient:
    """Fetch URLs through Firecrawl's scrape API."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 60.0,
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
        proxy: str = "auto",
        retries: int = 1,
        backoff: float = 2.0,
        timeout: float | None = None,
    ) -> str:
        """Fetch ``url`` via Firecrawl and return the raw response body.

        ``proxy='auto'`` lets Firecrawl escalate to stealth/residential proxies
        if a basic fetch is blocked (BSE needs this). Returns the first non-empty
        of the rawHtml / html / markdown fields. Raises :class:`FirecrawlError`.
        """
        if not self._api_key:
            raise FirecrawlError("no Firecrawl API key configured")

        payload = {
            "url": url,
            "formats": ["rawHtml"],
            "onlyMainContent": False,
            "proxy": proxy,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self._session.post(
                    FIRECRAWL_SCRAPE_URL,
                    json=payload,
                    headers=headers,
                    timeout=timeout or self._timeout,
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
