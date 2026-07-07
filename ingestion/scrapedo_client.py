"""Scrape.do client — STUB.

Scrape.do is a proxy/scraping API used to reliably fetch BSE pages that block
or throttle direct requests. It handles rotating proxies, JS rendering, and
geotargeting.

TODO (later step): implement real proxied fetching.
  - get(url): fetch a URL through the Scrape.do proxy, return HTML.
  - Support options like render=true (JS rendering) and geoCode=in.
  - Auth via SCRAPEDO_API_KEY (passed as a query param / token).

Docs: https://scrape.do/documentation/
"""

from __future__ import annotations

from config import Config


class ScrapedoClient:
    """Placeholder Scrape.do client. Real logic arrives in a later step."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @classmethod
    def from_config(cls, config: Config) -> "ScrapedoClient":
        return cls(api_key=config.scrapedo_api_key or "")

    def get(self, url: str, *, render: bool = False) -> str:
        """Fetch a URL through the Scrape.do proxy and return the HTML."""
        # TODO: build the Scrape.do request (token + target url + options)
        # and return the response body.
        raise NotImplementedError("ScrapedoClient.get is not implemented yet")
