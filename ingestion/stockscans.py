"""Live Stock Scan industry mapping (daksham repo — public, no token).

Fetched fresh EVERY run (~130 KB) so changes in daksham flow into the dashboard
automatically. This is what makes industry tagging "live".

Source: https://raw.githubusercontent.com/ceekay-munshot/daksham/main/public/data/stockscans-classification.json
Shape:  {"companies": {"<NSE_SYMBOL>": {"slug","symbol","industry","url"}}}
Keyed by NSE symbol (~951 companies, ~256 industries). It is a curated subset of
the market — symbols not present simply have no industry ("Unclassified").
"""

from __future__ import annotations

import time
from typing import Any

import requests

from config import Config  # noqa: F401 - kept for a uniform from_config-style call site

STOCKSCANS_URL = (
    "https://raw.githubusercontent.com/ceekay-munshot/daksham/main/"
    "public/data/stockscans-classification.json"
)


class StockScansError(RuntimeError):
    """Raised when the live mapping can't be fetched or parsed."""


def fetch_industry_by_symbol(
    config: Config | None = None,
    *,
    timeout: float = 45.0,
    retries: int = 2,
) -> dict[str, str]:
    """Return {NSE symbol -> industry} from the live Stock Scan mapping.

    Direct HTTPS to the public raw file (no token). Retries transient failures.
    Symbols are upppercased for matching; entries without an industry are
    dropped. Raises :class:`StockScansError` if nothing usable comes back.
    """
    headers = {
        "User-Agent": "orderbook-ingest/1.0",
        "Accept": "application/json, text/plain, */*",
    }
    session = requests.Session()
    last = "no attempt"
    for attempt in range(retries + 1):
        try:
            resp = session.get(STOCKSCANS_URL, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                return _parse(resp.text)
            last = f"HTTP {resp.status_code}"
        if attempt < retries:
            time.sleep(2.0 * (attempt + 1))
    raise StockScansError(f"could not fetch Stock Scan mapping: {last}")


def _parse(text: str) -> dict[str, str]:
    import json

    try:
        data: Any = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise StockScansError(f"mapping was not JSON: {str(text)[:120]}") from exc
    companies = data.get("companies") if isinstance(data, dict) else None
    if not isinstance(companies, dict) or not companies:
        raise StockScansError("mapping had no 'companies' object")
    out: dict[str, str] = {}
    for symbol, info in companies.items():
        if not symbol:
            continue
        industry = (info or {}).get("industry") if isinstance(info, dict) else None
        if industry and str(industry).strip():
            out[str(symbol).strip().upper()] = str(industry).strip()
    if not out:
        raise StockScansError("mapping parsed to 0 symbol->industry rows")
    return out
