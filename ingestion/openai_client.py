"""OpenAI client — field extraction from filing / PDF text.

Given the text of a BSE filing (the summary, or the full PDF text fetched by
Firecrawl in the enrichment step), OpenAI extracts the order fields the dashboard
shows. We call the Chat Completions REST API directly with ``requests`` (no SDK).

The prompt is deliberately strict: extract ONLY what is explicitly stated in the
text, return the literal string ``"not specified"`` when a field is absent, and
never guess or calculate a number. Normalization of the returned phrases into
crore / months happens in code (see bse_client), so a number is only ever stored
if it literally appears in the filing.

Auth via ``OPENAI_API_KEY``. Model defaults to ``gpt-4o-mini`` (override with
``OPENAI_MODEL``).

Docs: https://platform.openai.com/docs/api-reference/chat
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from config import Config

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
# BSE order filings are short; 12k chars is plenty and keeps token cost tiny.
MAX_INPUT_CHARS = 12000

SYSTEM_PROMPT = (
    "You extract structured facts from Indian stock-exchange (BSE) order-win "
    "filings. Extract ONLY what is explicitly stated in the provided text. Do "
    "NOT infer, calculate, convert, or guess. If a field is not explicitly "
    'stated, return exactly the string "not specified" for it. Never invent a '
    "number, amount, currency, or date.\n\n"
    "Return a JSON object with exactly these keys:\n"
    '  "order_value": the exact phrase stating the order/contract value, copied '
    'verbatim from the text (e.g. "Rs. 125.50 Crore", "₹ 47.38 Lakhs"). Use '
    '"not specified" if no monetary value is stated.\n'
    '  "duration": the exact phrase stating the execution period / timeline / '
    'completion time (e.g. "24 months", "within 2 years from the date of "'
    'award"). Use "not specified" if none is stated.\n'
    '  "awarder": the name of the entity that awarded or placed the order (the '
    'customer / client), e.g. "Ministry of Railways", "NTPC Limited". Use "not '
    'specified" if it is not clearly stated.\n'
    '  "confidence": a number from 0 to 1 for how clearly these are stated.\n\n'
    "Copy phrases verbatim. Do not add units, numbers, or names not in the text."
)


class OpenAIError(RuntimeError):
    """Raised when an OpenAI request fails or returns an unexpected shape."""


@dataclass
class Extraction:
    """Fields extracted from one filing's text — raw phrases, not yet normalized.

    ``order_value`` / ``duration`` / ``awarder`` are the verbatim phrases (or
    ``None`` when the model said "not specified"). Normalization to crore/months
    is done by the caller via bse_client helpers.
    """

    order_value: str | None
    duration: str | None
    awarder: str | None
    confidence: float | None
    model: str
    raw: dict[str, Any] = field(default_factory=dict)


# Values the model may use for "absent" — all collapse to None.
_NOT_SPECIFIED = {"not specified", "not stated", "n/a", "na", "none", "unknown", "-"}


def _clean(value: Any) -> str | None:
    """Normalize a model field to a stripped string, or None when it's absent."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.casefold() in _NOT_SPECIFIED:
        return None
    return s


class OpenAIClient:
    """Extract order fields from filing text via the OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str | None = None,
        timeout: float = 60.0,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
        self._timeout = timeout
        self._session = session or requests.Session()

    @classmethod
    def from_config(cls, config: Config, **kwargs: Any) -> "OpenAIClient":
        return cls(api_key=config.openai_api_key or "", **kwargs)

    @property
    def model(self) -> str:
        return self._model

    def extract(
        self,
        text: str,
        *,
        retries: int = 2,
        backoff: float = 2.0,
    ) -> Extraction:
        """Extract order_value / duration / awarder phrases from ``text``.

        Retries transient errors (429/5xx, network); raises :class:`OpenAIError`
        on a non-retryable error or after exhausting retries. The returned
        phrases are verbatim — normalize them with bse_client's
        ``value_phrase_to_crore`` / ``duration_to_months``.
        """
        if not self._api_key:
            raise OpenAIError("no OpenAI API key configured")
        snippet = (text or "").strip()[:MAX_INPUT_CHARS]
        if not snippet:
            raise OpenAIError("no text to extract from")

        payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Filing text:\n\n" + snippet},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self._session.post(
                    OPENAI_CHAT_URL,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:
                last_err = exc
            else:
                if resp.status_code == 200:
                    return self._parse_response(resp.json())
                last_err = OpenAIError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
                if resp.status_code not in (429, 500, 502, 503, 504):
                    raise last_err
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
        raise OpenAIError(
            f"OpenAI request failed after {retries + 1} attempt(s): {last_err}"
        )

    def _parse_response(self, body: dict[str, Any]) -> Extraction:
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenAIError(
                f"unexpected OpenAI response shape: {str(body)[:200]}"
            ) from exc
        try:
            data = json.loads(content)
        except (ValueError, TypeError) as exc:
            raise OpenAIError(
                f"OpenAI returned non-JSON content: {str(content)[:200]}"
            ) from exc
        if not isinstance(data, dict):
            raise OpenAIError(f"OpenAI JSON was not an object: {str(data)[:200]}")

        conf = data.get("confidence")
        try:
            confidence = float(conf) if conf is not None else None
        except (ValueError, TypeError):
            confidence = None

        return Extraction(
            order_value=_clean(data.get("order_value")),
            duration=_clean(data.get("duration")),
            awarder=_clean(data.get("awarder")),
            confidence=confidence,
            model=self._model,
            raw=data,
        )
