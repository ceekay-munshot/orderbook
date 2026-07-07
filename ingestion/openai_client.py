"""OpenAI client — STUB.

Given the text of a BSE filing, OpenAI extracts the five structured fields that
power the dashboard:
    value · awarder · duration · target_industry · description

TODO (later step): implement real extraction.
  - extract_order(filing_text): call the OpenAI API with a strict prompt /
    JSON schema and return the five fields (plus confidence / evidence spans).
  - Use structured outputs (response_format=json_schema) for reliability.
  - Auth via OPENAI_API_KEY.

Docs: https://platform.openai.com/docs/
"""

from __future__ import annotations

from dataclasses import dataclass

from config import Config


@dataclass
class ExtractedOrder:
    """The five fields extracted from a single filing."""

    value: str
    awarder: str
    duration: str
    target_industry: str
    description: str


class OpenAIClient:
    """Placeholder OpenAI client. Real logic arrives in a later step."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @classmethod
    def from_config(cls, config: Config) -> "OpenAIClient":
        return cls(api_key=config.openai_api_key or "")

    def extract_order(self, filing_text: str) -> ExtractedOrder:
        """Extract the five order fields from filing text."""
        # TODO: call the OpenAI API with a structured-output schema and map the
        # response into an ExtractedOrder.
        raise NotImplementedError(
            "OpenAIClient.extract_order is not implemented yet"
        )
