"""BSE official industry classification (SEBI industry, one per scrip code).

The FALLBACK industry source. stockscans.in (ingestion/stockscans.py) is richer
and stays primary, but it only tracks ~94% of the market; the remaining tail —
small/illiquid names that can still file an order-win announcement — has no
stockscans entry and would otherwise stay "Unclassified".

BSE, by contrast, publishes a SEBI industry for EVERY listed scrip, keyed by the
6-digit scrip code (the same id `orders` and `security_master` are keyed by). So
this fills the gap and lets industry tagging reach every Indian listed company.

Source: the per-scrip "company header" endpoint
    https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w?quotetype=EQ&scripcode=<code>&seriesid=
which returns {"Industry", "Sector", "IndustryNew", ...}. One call per scrip,
fetched concurrently. Best-effort: a scrip that doesn't resolve is simply omitted
(it stays Unclassified, exactly as before) — this never raises.
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any

import requests

COMHEADER_URL = "https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Referer": "https://www.bseindia.com/",
}


def _pick_industry(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (industry, sub_industry) from a ComHeadernew payload.

    Industry is BSE's most granular label (e.g. "Refineries & Marketing"),
    falling back to the SEBI macro industry then the sector when it's blank.
    Sector is kept as the sub-industry for extra grouping, dropped when it just
    repeats the industry.
    """
    def clean(key: str) -> str:
        return str(data.get(key) or "").strip()

    industry = clean("Industry") or clean("IndustryNew") or clean("Sector")
    if not industry:
        return None, None
    sector = clean("Sector")
    sub = sector if sector and sector != industry else None
    return industry, sub


def _fetch_one(scrip_code: str, *, timeout: float = 20.0, retries: int = 1):
    """Return (scrip_code, {'industry','sub_industry'} | None). Best-effort."""
    params = {"quotetype": "EQ", "scripcode": scrip_code, "seriesid": ""}
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                COMHEADER_URL, params=params, headers=_HEADERS, timeout=timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    industry, sub = _pick_industry(data)
                    if industry:
                        return scrip_code, {"industry": industry, "sub_industry": sub}
                return scrip_code, None
        except (requests.RequestException, ValueError):
            pass
        if attempt < retries:
            time.sleep(0.5 * (attempt + 1))
    return scrip_code, None


def fetch_bse_industries(
    scrip_codes: list[str],
    *,
    max_workers: int = 16,
) -> dict[str, dict[str, str | None]]:
    """Return {scrip_code -> {'industry','sub_industry'}} from BSE's per-scrip
    classification endpoint, fetched concurrently.

    Best-effort by design: this is a fallback used only for the companies the
    primary (stockscans) source didn't classify, so scrips that don't resolve
    are omitted rather than raising. An empty input returns an empty dict.
    """
    wanted = [str(s).strip() for s in scrip_codes if str(s or "").strip()]
    if not wanted:
        return {}
    result: dict[str, dict[str, str | None]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for scrip, info in pool.map(_fetch_one, wanted):
            if info:
                result[scrip] = info
    return result
