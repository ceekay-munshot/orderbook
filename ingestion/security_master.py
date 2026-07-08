"""Company translator: BSE scrip code <-> NSE symbol <-> ISIN.

Builds the `security_master` from two official public lists, joined on ISIN (the
identifier both exchanges publish):

  * NSE equity list  — https://archives.nseindia.com/content/equities/EQUITY_L.csv
      columns: SYMBOL, "NAME OF COMPANY", "ISIN NUMBER"  -> NSE symbol <-> ISIN
  * BSE scrip list   — https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w
      (segment=Equity, status=Active); fields: SCRIP_CD, ISIN_NUMBER, Issuer_Name
      -> BSE scrip code <-> ISIN

Both are fetched directly (datacenter IPs work); if a CI runner is ever blocked,
each falls back to Scrape.do — the same pattern as the BSE announcements reader.
The join keys BSE scrip code to NSE symbol via ISIN. Companies with a BSE scrip
+ ISIN but no NSE listing are kept with nse_symbol=None.

This module only BUILDS the translator; attaching an industry to orders is the
next step.
"""

from __future__ import annotations

import csv
import io
import json
import time
from typing import Any

import requests

from config import Config
from scrapedo_client import ScrapedoClient, ScrapedoError

NSE_EQUITY_CSV = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
BSE_SCRIP_API = (
    "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
    "?Group=&Scripcode=&industry=&segment=Equity&status=Active"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/csv, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
}

# The three mappings we assert resolve correctly after every build.
KNOWN_MAPPINGS: tuple[tuple[str, str, str], ...] = (
    ("500325", "RELIANCE", "INE002A01018"),
    ("500209", "INFY", "INE009A01021"),
    ("532540", "TCS", "INE467B01029"),
)


class SecurityMasterError(RuntimeError):
    """Raised when a source can't be fetched or parsed."""


def _fetch_text(
    url: str,
    config: Config,
    *,
    validate,
    timeout: float = 45.0,
    retries: int = 2,
) -> str:
    """Fetch ``url`` as text, direct first (with retries) then via Scrape.do.

    ``validate(text) -> bool`` decides whether a response is the real payload
    (not an error/anti-bot page); the first response that validates is returned.
    Raises :class:`SecurityMasterError` if nothing usable comes back.
    """
    session = requests.Session()
    last = "no attempt"
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, headers=_HEADERS, timeout=timeout)
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200 and validate(resp.text):
                return resp.text
            last = f"HTTP {resp.status_code}, {len(resp.text)} chars (unrecognized)"
        if attempt < retries:
            time.sleep(2.0 * (attempt + 1))

    if config.scrapedo_api_key:
        try:
            text = ScrapedoClient.from_config(config).get(
                url, super_proxy=True, geo_code="in", extra_headers=_HEADERS
            )
        except ScrapedoError as exc:
            last = f"scrape.do: {exc}"
        else:
            if validate(text):
                print(f"    [{url.split('//')[-1][:32]}...] fetched via Scrape.do")
                return text
            last = f"scrape.do returned {len(text)} chars (unrecognized)"

    raise SecurityMasterError(f"could not fetch {url}: {last}")


def normalize_isin(value: Any) -> str:
    """Uppercase + trim an ISIN; '' when missing."""
    return str(value).strip().upper() if value else ""


def fetch_nse_isin_to_symbol(config: Config) -> dict[str, str]:
    """Return {ISIN -> NSE symbol} from the NSE equity list."""
    text = _fetch_text(
        NSE_EQUITY_CSV, config, validate=lambda t: "SYMBOL" in (t[:120].upper())
    )
    mapping: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(text)):
        clean = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        isin = normalize_isin(clean.get("ISIN NUMBER"))
        symbol = clean.get("SYMBOL", "")
        if isin and symbol:
            mapping[isin] = symbol
    if not mapping:
        raise SecurityMasterError("NSE list parsed to 0 ISIN->symbol rows")
    return mapping


def fetch_bse_scrips(config: Config) -> list[dict[str, Any]]:
    """Return the BSE active-equity scrip rows (list of dicts)."""
    text = _fetch_text(
        BSE_SCRIP_API, config, validate=lambda t: "SCRIP_CD" in (t[:500])
    )
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise SecurityMasterError(f"BSE scrip list was not JSON: {str(text)[:120]}") from exc
    if not isinstance(data, list) or not data:
        raise SecurityMasterError("BSE scrip list JSON was empty / not a list")
    return data


def _norm_scrip(value: Any) -> str:
    s = str(value or "").strip()
    return s.zfill(6) if s.isdigit() else s  # keep leading zeros


def build_master(config: Config) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Fetch both sources and join on ISIN.

    Returns (rows, stats). Each row is {bse_scrip_code, isin, nse_symbol,
    company_name, source}; nse_symbol is None for BSE-only companies. Rows are
    deduped by BSE scrip code.
    """
    isin_to_symbol = fetch_nse_isin_to_symbol(config)
    bse_rows = fetch_bse_scrips(config)

    master: dict[str, dict[str, Any]] = {}
    for row in bse_rows:
        scrip = _norm_scrip(row.get("SCRIP_CD"))
        isin = normalize_isin(row.get("ISIN_NUMBER"))
        if not scrip or not isin:
            continue
        name = (row.get("Issuer_Name") or row.get("Scrip_Name") or "").strip() or None
        symbol = isin_to_symbol.get(isin) or None
        # BSE's own ticker (scrip_id), e.g. 500002 -> "ABB". Used to join
        # BSE-only companies to stockscans, which keys BSE by ticker ("BSE:ABB").
        bse_symbol = (str(row.get("scrip_id") or "").strip().upper()) or None
        master[scrip] = {
            "bse_scrip_code": scrip,
            "isin": isin,
            "nse_symbol": symbol,
            "bse_symbol": bse_symbol,
            "company_name": name,
            "source": "bse+nse" if symbol else "bse",
        }

    rows = list(master.values())
    with_nse = sum(1 for r in rows if r["nse_symbol"])
    stats = {
        "nse_rows": len(isin_to_symbol),
        "bse_rows": len(bse_rows),
        "total": len(rows),
        "with_nse": with_nse,
        "bse_only": len(rows) - with_nse,
    }
    return rows, stats


def verify(rows: list[dict[str, Any]]) -> list[tuple[str, str, str, dict | None, bool]]:
    """Check the KNOWN_MAPPINGS against built rows.

    Returns a list of (scrip, expected_symbol, expected_isin, row_or_None, ok).
    """
    by_scrip = {r["bse_scrip_code"]: r for r in rows}
    out: list[tuple[str, str, str, dict | None, bool]] = []
    for scrip, symbol, isin in KNOWN_MAPPINGS:
        row = by_scrip.get(scrip) or by_scrip.get(_norm_scrip(scrip))
        ok = bool(row) and row.get("nse_symbol") == symbol and row.get("isin") == isin
        out.append((scrip, symbol, isin, row, ok))
    return out
