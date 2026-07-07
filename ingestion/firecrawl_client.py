"""Firecrawl client — STUB.

Firecrawl is used to fetch and parse web pages and PDFs (BSE announcement
attachments are PDFs; Firecrawl can parse them into clean text/markdown).

TODO (later step): implement real fetching + parsing.
  - scrape(url): fetch a page, return cleaned markdown/text + metadata.
  - parse_pdf(url): fetch a PDF filing and return extracted text.
  - Handle Firecrawl's async job polling and rate limits.
  - Auth via FIRECRAWL_API_KEY.

Docs: https://docs.firecrawl.dev/
"""

from __future__ import annotations

from config import Config


class FirecrawlClient:
    """Placeholder Firecrawl client. Real logic arrives in a later step."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @classmethod
    def from_config(cls, config: Config) -> "FirecrawlClient":
        return cls(api_key=config.firecrawl_api_key or "")

    def scrape(self, url: str) -> str:
        """Fetch and parse a page into text/markdown."""
        # TODO: call the Firecrawl scrape endpoint and return parsed content.
        raise NotImplementedError("FirecrawlClient.scrape is not implemented yet")

    def parse_pdf(self, url: str) -> str:
        """Fetch and parse a PDF filing into text."""
        # TODO: call Firecrawl to parse the PDF and return extracted text.
        raise NotImplementedError(
            "FirecrawlClient.parse_pdf is not implemented yet"
        )
