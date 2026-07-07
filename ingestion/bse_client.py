"""BSE corporate-announcements reader.

Fetches order-related filings from BSE's public announcements JSON API, filters
them to order wins, and parses each into the `orders` table columns (leaving the
5 extracted fields NULL — those are filled in Steps 4-5). Fetches go through
Scrape.do so datacenter IPs aren't blocked; a direct best-effort fetch is used
only as a fallback for local testing.

BSE endpoint (JSON, no JS rendering needed):
  https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w
  ?pageno=1&strCat=-1&strPrevDate=YYYYMMDD&strToDate=YYYYMMDD
  &strScrip=&strSearch=P&strType=C

Response is a JSON object: {"Table": [ ...announcements... ], "Table1": [...] }.
When there are no rows (or the caller is IP-blocked) BSE returns the JSON string
"No Record Found!" instead of an object.
"""

from __future__ import annotations

import datetime
import html
import json
import re
import time
from typing import Any, Callable, Iterable

import requests

from config import Config
from firecrawl_client import FirecrawlClient
from scrapedo_client import ScrapedoClient

# A fetcher fetches a URL and returns the raw response body text.
Fetcher = tuple[str, Callable[[str], str]]

BSE_ANN_API = "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
ATTACH_LIVE_BASE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
ATTACH_HIS_BASE = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/"

# Sent with each fetch (forwarded by Scrape.do / Firecrawl). BSE's API serves
# the Angular website HTML unless the request looks like an XHR from the SPA:
# it checks Referer/Origin and expects application/json.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/corporates/ann.html",
    "X-Requested-With": "XMLHttpRequest",
}

# --- order classification ----------------------------------------------------

# PRIMARY: exact BSE subcategory.
ORDER_SUBCATEGORY = "Award of Order / Receipt of Order"

# FALLBACK: keywords for order filings mis-filed under General/Company Update.
ORDER_KEYWORDS = (
    "order",
    "contract",
    "bags",
    "bagged",
    "wins",
    "won",
    "awarded",
    "award of",
    "receipt of order",
    "letter of award",
    "loa",
    "letter of intent",
    "loi",
    "work order",
    "purchase order",
    "secures order",
    "receives order",
    "emerges as l1",
    "lowest bidder",
)

# Longest-first so multi-word phrases win over the bare word "order" in logging.
_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(ORDER_KEYWORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def classify(ann: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (rule, detail) — rule is 'subcat', 'keyword', or None.

    'subcat'  -> SUBCATNAME exactly equals the order subcategory.
    'keyword' -> a keyword matched the subject/headline (detail = the keyword).
    """
    subcat = (ann.get("SUBCATNAME") or "").strip()
    if subcat.casefold() == ORDER_SUBCATEGORY.casefold():
        return "subcat", subcat

    text = " ".join(str(v) for v in (ann.get("NEWSSUB"), ann.get("HEADLINE")) if v)
    m = _KEYWORD_RE.search(text)
    if m:
        return "keyword", m.group(1).lower()
    return None, None


# --- parsing -----------------------------------------------------------------

def to_iso8601(raw: Any) -> str | None:
    """Convert a BSE datetime string to ISO 8601 (naive). Keeps raw if unparseable."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None).isoformat()
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
    ):
        try:
            return datetime.datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue
    return s  # unparseable — keep the raw value rather than lose it


def build_attachment_url(name: Any, *, historical: bool = False) -> str | None:
    """Build the BSE PDF URL from an attachment filename (AttachLive by default)."""
    if not name or not str(name).strip():
        return None
    base = ATTACH_HIS_BASE if historical else ATTACH_LIVE_BASE
    return base + str(name).strip()


def _scrip_to_str(scrip: Any) -> str | None:
    if scrip is None:
        return None
    s = str(scrip).strip()
    if not s:
        return None
    return s.zfill(6) if s.isdigit() else s  # keep 6-digit form / leading zeros


def parse_announcement(ann: dict[str, Any]) -> dict[str, Any]:
    """Map one BSE announcement row into `orders` columns (5 extracted fields NULL)."""
    scrip_code = _scrip_to_str(ann.get("SCRIP_CD"))
    headline = (str(ann.get("NEWSSUB") or ann.get("HEADLINE") or "")).strip() or None
    subcat = (str(ann.get("SUBCATNAME") or "")).strip() or None
    company = (str(ann.get("SLONGNAME") or "")).strip()
    if not company:
        company = f"BSE:{scrip_code}" if scrip_code else "Unknown company"
    newsid = ann.get("NEWSID")
    filed_at = to_iso8601(
        ann.get("NEWS_DT") or ann.get("DissemDT") or ann.get("News_submission_dt")
    )
    return {
        # identity
        "company_name": company,
        "bse_scrip_code": scrip_code,
        "nse_symbol": None,
        "isin": None,
        # 5 extracted fields — filled by Steps 4-5 (description temporarily = headline)
        "order_value_text": None,
        "order_value_crore": None,
        "awarder": None,
        "duration_text": None,
        "duration_months": None,
        "target_industry": None,
        "description": headline,
        # evidence / provenance
        "exchange": "BSE",
        "category": subcat,
        "headline": headline,
        "attachment_url": build_attachment_url(ann.get("ATTACHMENTNAME")),
        "source_label": "BSE Filing",
        "raw_text": None,
        "extraction_confidence": None,
        "extraction_model": None,
        # identity / dedup
        "bse_announcement_id": str(newsid).strip() if newsid is not None else None,
        "filed_at": filed_at,
    }


# --- fetching ----------------------------------------------------------------

def build_ann_url(page: int, from_date: datetime.date, to_date: datetime.date) -> str:
    """Build the BSE AnnGetData URL for one page of a date range."""
    return (
        f"{BSE_ANN_API}?pageno={page}&strCat=-1"
        f"&strPrevDate={from_date.strftime('%Y%m%d')}"
        f"&strToDate={to_date.strftime('%Y%m%d')}"
        "&strScrip=&strSearch=P&strType=C"
    )


def _first_json(text: str | None) -> Any:
    """Best-effort parse of a BSE/proxy response body into a JSON value.

    Handles: raw JSON; the string "No Record Found!"; and JSON wrapped in HTML
    (e.g. when a proxy like Firecrawl returns the body inside a page).
    """
    if not text:
        return None
    s = text.strip()
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        pass
    unescaped = html.unescape(s)
    try:
        return json.loads(unescaped)
    except (ValueError, TypeError):
        pass
    start, end = unescaped.find("{"), unescaped.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(unescaped[start : end + 1])
        except (ValueError, TypeError):
            pass
    return None


def parse_table(text: str) -> list[dict[str, Any]]:
    """Extract the 'Table' rows from a BSE response body (handles 'No Record Found!')."""
    data = _first_json(text)
    if isinstance(data, dict):
        table = data.get("Table")
        return table if isinstance(table, list) else []
    return []  # e.g. the string "No Record Found!"


def build_fetchers(config: Config, *, timeout: float = 30.0) -> list[Fetcher]:
    """Build the ordered fetcher chain from available API keys.

    Order: Scrape.do (residential) -> Firecrawl -> direct. BSE blocks datacenter
    IPs, so Scrape.do uses `super=true` (residential) + geoCode=in, and Firecrawl
    uses proxy=auto (escalates to stealth). Direct is a keyless last resort.
    """
    fetchers: list[Fetcher] = []

    if config.scrapedo_api_key:
        scrapedo = ScrapedoClient.from_config(config)

        def _via_scrapedo(url: str) -> str:
            return scrapedo.get(
                url, super_proxy=True, geo_code="in", extra_headers=BROWSER_HEADERS
            )

        fetchers.append(("scrape.do", _via_scrapedo))

    if config.firecrawl_api_key:
        firecrawl = FirecrawlClient.from_config(config)

        def _via_firecrawl(url: str) -> str:
            # Forward the XHR headers so BSE returns API JSON, not the SPA HTML.
            return firecrawl.scrape(url, headers=BROWSER_HEADERS)

        fetchers.append(("firecrawl", _via_firecrawl))

    _session = requests.Session()

    def _via_direct(url: str) -> str:
        return _session.get(url, headers=BROWSER_HEADERS, timeout=timeout).text

    fetchers.append(("direct", _via_direct))
    return fetchers


class BSEReader:
    """Pages through BSE announcements, trying a chain of fetchers until one works."""

    def __init__(
        self,
        fetchers: list[Fetcher],
        *,
        page_delay: float = 1.0,
        max_pages: int = 50,
        sample_len: int = 300,
    ) -> None:
        self._fetchers = fetchers
        self._page_delay = page_delay
        self._max_pages = max_pages
        self._sample_len = sample_len
        self.source: str | None = None  # which fetcher produced the rows

    def _probe(
        self, url: str
    ) -> tuple[str, Callable[[str], str], list[dict[str, Any]]] | None:
        """Try each fetcher on `url`; return the first that yields rows (logged)."""
        for name, fetch in self._fetchers:
            try:
                text = fetch(url)
            except Exception as exc:  # noqa: BLE001 - log and try the next fetcher
                print(f"  [{name}] error: {type(exc).__name__}: {exc}")
                continue
            rows = parse_table(text)
            sample = " ".join((text or "").split())[: self._sample_len]
            print(f"  [{name}] {len(text or '')} chars -> {len(rows)} rows | sample: {sample!r}")
            if rows:
                return name, fetch, rows
        return None

    def fetch_range(
        self, from_date: datetime.date, to_date: datetime.date
    ) -> list[dict[str, Any]]:
        """Fetch all announcement rows for [from_date, to_date], paging until done."""
        probe = self._probe(build_ann_url(1, from_date, to_date))
        if probe is None:
            return []
        name, fetch, first_rows = probe
        self.source = name

        rows: list[dict[str, Any]] = list(first_rows)
        seen_ids = {str(r.get("NEWSID")) for r in first_rows}
        total_pages = first_rows[0].get("TotalPageCnt")

        page = 2
        while page <= self._max_pages and not (total_pages and page > int(total_pages)):
            time.sleep(self._page_delay)
            try:
                text = fetch(build_ann_url(page, from_date, to_date))
            except Exception as exc:  # noqa: BLE001
                print(f"  [{name}] page {page} error: {exc}")
                break
            fresh = [r for r in parse_table(text) if str(r.get("NEWSID")) not in seen_ids]
            if not fresh:
                break
            for r in fresh:
                seen_ids.add(str(r.get("NEWSID")))
            rows.extend(fresh)
            page += 1

        print(f"  -> fetched {len(rows)} rows via {name}")
        return rows


def iter_matched(
    announcements: Iterable[dict[str, Any]],
) -> Iterable[tuple[dict[str, Any], str, str | None]]:
    """Yield (parsed_order, rule, detail) for each order-matching announcement."""
    for ann in announcements:
        rule, detail = classify(ann)
        if rule is None:
            continue
        yield parse_announcement(ann), rule, detail
