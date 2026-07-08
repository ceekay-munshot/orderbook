"""Live Stock Scan industry mapping (daksham repo — public, no token).

Fetched fresh EVERY run (~130 KB) so changes in daksham flow into the dashboard
automatically. This is what makes industry tagging "live".

Source: https://raw.githubusercontent.com/ceekay-munshot/daksham/main/public/data/stockscans-classification.json
Shape:  {"companies": {"<NSE_SYMBOL>": {"slug","symbol","industry","url"}}}
Keyed by NSE symbol (~951 companies, ~256 industries). It is a curated subset of
the market — symbols not present simply have no industry ("Unclassified").
"""

from __future__ import annotations

import concurrent.futures
import html as html_lib
import re
import time
from typing import Any
from urllib.parse import quote

import requests

from config import Config  # noqa: F401 - kept for a uniform from_config-style call site

STOCKSCANS_URL = (
    "https://raw.githubusercontent.com/ceekay-munshot/daksham/main/"
    "public/data/stockscans-classification.json"
)

# The FULL stockscans.in classification (5,800+ companies, ~half BSE-listed),
# vs the ~951-company daksham subset above. Universe from the sitemap; industry
# from a public per-company JSON API (no auth). Keys are EXCHANGE:SYMBOL, e.g.
# "NSE:INFY", "BSE:SATTRIX".
COMPANIES_SITEMAP = "https://www.stockscans.in/sitemaps/companies.xml"
SEARCH_COMPANY_URL = "https://www.stockscans.in/api/company/scans/search-company/"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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


# --- FULL stockscans.in pull (per-company JSON API) --------------------------

def fetch_company_ids(*, timeout: float = 45.0, retries: int = 2) -> list[str]:
    """Return every EXCHANGE:SYMBOL id from the stockscans companies sitemap."""
    headers = {"User-Agent": _BROWSER_UA, "Accept": "application/xml, text/xml, */*"}
    last = "no attempt"
    for attempt in range(retries + 1):
        try:
            resp = requests.get(COMPANIES_SITEMAP, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200 and "<loc>" in resp.text:
                ids: list[str] = []
                seen: set[str] = set()
                for m in re.finditer(r"/company/([^<]+)</loc>", resp.text):
                    cid = html_lib.unescape(m.group(1)).strip()
                    if cid and cid not in seen:
                        seen.add(cid)
                        ids.append(cid)
                if ids:
                    return ids
                last = "sitemap parsed 0 ids"
            else:
                last = f"HTTP {resp.status_code}"
        if attempt < retries:
            time.sleep(2.0 * (attempt + 1))
    raise StockScansError(f"could not fetch companies sitemap: {last}")


def _fetch_one_industry(company_id: str, *, timeout: float = 20.0, retries: int = 2):
    """Return (company_id, industry|None) from the per-company API. Best-effort."""
    headers = {"User-Agent": _BROWSER_UA, "Accept": "application/json, */*"}
    url = SEARCH_COMPANY_URL + quote(company_id, safe=":&")
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                meta = data.get("metaRatios") if isinstance(data, dict) else None
                industry = (meta or {}).get("Industry") if isinstance(meta, dict) else None
                if industry and str(industry).strip():
                    return company_id, str(industry).strip()
                return company_id, None
        except (requests.RequestException, ValueError):
            pass
        if attempt < retries:
            time.sleep(0.5 * (attempt + 1))
    return company_id, None


def fetch_full_stockscans(
    config: Config | None = None,
    *,
    max_workers: int = 24,
    min_expected: int = 2000,
) -> dict[str, str]:
    """Pull the FULL classification: {companyId -> industry} for every company in
    the sitemap (keys like 'NSE:INFY', 'BSE:SATTRIX').

    Universe from the sitemap; industry from the per-company JSON API, fetched
    concurrently. Raises :class:`StockScansError` if too few resolve (so the
    caller can fall back to the daksham mapping) — it never returns a thin result.
    """
    company_ids = fetch_company_ids()
    result: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for cid, industry in pool.map(_fetch_one_industry, company_ids):
            if industry:
                result[cid] = industry
    if len(result) < min_expected:
        raise StockScansError(
            f"full pull resolved only {len(result)}/{len(company_ids)} companies "
            f"(< {min_expected}); treating as failed"
        )
    return result
