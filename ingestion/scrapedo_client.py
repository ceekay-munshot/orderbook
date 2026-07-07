"""Scrape.do client — proxied HTTP fetch.

Scrape.do is a proxy/scraping API used to fetch pages that block datacenter IPs
(e.g. BSE's JSON APIs return "No Record Found!" to non-residential IPs). We call
the target URL through Scrape.do so requests come from rotating proxies.

Endpoint:  https://api.scrape.do/?token=<TOKEN>&url=<TARGET-URL>
Options used here:
  - render=true        -> JS rendering (NOT needed for JSON APIs)
  - customHeaders=true -> forward the headers we send (e.g. Referer) to the target

Docs: https://scrape.do/documentation/
"""

from __future__ import annotations

import time

import requests

from config import Config

SCRAPEDO_ENDPOINT = "https://api.scrape.do/"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ScrapedoError(RuntimeError):
    """Raised when a Scrape.do request fails (after retries)."""


class ScrapedoClient:
    """Fetch URLs through the Scrape.do proxy."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 45.0,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._session = session or requests.Session()

    @classmethod
    def from_config(cls, config: Config) -> "ScrapedoClient":
        return cls(api_key=config.scrapedo_api_key or "")

    def get(
        self,
        url: str,
        *,
        render: bool = False,
        super_proxy: bool = False,
        geo_code: str | None = None,
        extra_headers: dict[str, str] | None = None,
        retries: int = 2,
        backoff: float = 2.0,
        timeout: float | None = None,
    ) -> str:
        """Fetch ``url`` through Scrape.do and return the target's response body.

        ``super_proxy=True`` uses residential/mobile proxies (needed for sites
        that block datacenter IPs, like BSE); ``geo_code`` geo-targets (e.g.
        "in"). Retries transient failures (network errors + 429/5xx) up to
        ``retries`` times with linear backoff. Raises :class:`ScrapedoError`.
        """
        if not self._api_key:
            raise ScrapedoError("no Scrape.do API key configured")

        params: dict[str, str] = {"token": self._api_key, "url": url}
        if render:
            params["render"] = "true"
        if super_proxy:
            params["super"] = "true"
        if geo_code:
            params["geoCode"] = geo_code
        headers: dict[str, str] = {}
        if extra_headers:
            # Ask Scrape.do to forward our headers (Referer/User-Agent) to BSE.
            params["customHeaders"] = "true"
            headers = dict(extra_headers)

        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self._session.get(
                    SCRAPEDO_ENDPOINT,
                    params=params,
                    headers=headers,
                    timeout=timeout or self._timeout,
                )
            except requests.RequestException as exc:
                last_err = exc
            else:
                if resp.status_code == 200:
                    return resp.text
                last_err = ScrapedoError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
                if resp.status_code not in _RETRYABLE_STATUS:
                    raise last_err
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
        raise ScrapedoError(
            f"Scrape.do request failed after {retries + 1} attempt(s): {last_err}"
        )
