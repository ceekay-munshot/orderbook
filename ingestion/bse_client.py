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
from urllib.parse import quote

import requests

from config import Config
from firecrawl_client import FirecrawlClient
from scrapedo_client import ScrapedoClient

# A fetcher fetches a URL and returns the raw response body text.
Fetcher = tuple[str, Callable[[str], str]]

# Announcements JSON API. NOTE: it is AnnSubCategoryGetData/w — NOT AnnGetData/w
# (which returns "No Record Found!") — it needs a `subcategory` param, and the
# date range must be a SINGLE day (wider ranges return {} or a "Date range
# exceeded threshold" error), so we query day by day.
BSE_ANN_API = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
# The announcements page — loaded first so Firecrawl can call the API from its
# JS context (correct Origin/Referer/cookies).
BSE_SITE = "https://www.bseindia.com/corporates/ann.html"
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

# PRIMARY: exact BSE subcategory. We ask BSE to filter to this directly (its own
# dropdown), so it returns ONLY order wins — clean, no keyword noise.
ORDER_CATEGORY = "Company Update"
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


# Filings BSE files under "Award of Order / Receipt of Order" that are NOT
# commercial order wins — court / tribunal / insolvency / arbitration rulings.
# The word "order" is overloaded (a court ORDER vs a purchase ORDER), so these
# land in the same subcategory. They have no value / customer / duration, so we
# keep them OUT of the order book.
_NONCOMMERCIAL_RE = re.compile(
    r"\b(?:nclt|nclat|national company law tribunal|appellate tribunal|tribunal|"
    r"arbitration|arbitral|insolvency|winding[\s-]?up|liquidation|liquidator|"
    r"moratorium|resolution plan|debt recovery|\bibc\b|corporate insolvency)\b",
    re.IGNORECASE,
)


def text_is_noncommercial(text: str | None) -> bool:
    """True if ``text`` reads like a legal/court/tribunal order, not an order win."""
    return bool(text and _NONCOMMERCIAL_RE.search(text))


def is_noncommercial(ann: dict[str, Any]) -> bool:
    """True if a BSE announcement is a legal/court order, not a commercial win."""
    text = " ".join(
        str(v)
        for v in (ann.get("NEWSSUB"), ann.get("HEADLINE"), ann.get("SUBCATNAME"))
        if v
    )
    return text_is_noncommercial(text)


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


# Rupee amount in the announcement text, e.g. "Rs. 10.85 Crores", "Rs. 47.38
# Lakhs", "Rs. 36,95,760" (plain rupees). Unit is optional.
_VALUE_RE = re.compile(
    r"(?:rs\.?|inr|₹)\s*(\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*(crores?|cr|lakhs?|lacs?|millions?|mn)\b)?",
    re.IGNORECASE,
)


def parse_value(text: str | None) -> tuple[str | None, float | None]:
    """Pull an order value out of the summary text, if it states one.

    Returns (raw_text, value_in_crore). First rupee amount wins (the headline
    usually leads with it). Returns (None, None) when no amount is stated — those
    get filled from the PDF later (Steps 4-5).
    """
    if not text:
        return None, None
    m = _VALUE_RE.search(text)
    if not m:
        return None, None
    num = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    if unit.startswith("cr"):
        crore = num
    elif unit.startswith(("lakh", "lac")):
        crore = num / 100
    elif unit.startswith(("million", "mn")):
        crore = num * 0.1
    else:  # plain rupees
        crore = num / 1e7
    return m.group(0).strip(), round(crore, 4)


# --- normalizers for LLM-extracted phrases -----------------------------------
# The PDF-enrichment step (Step 3) asks OpenAI for the *verbatim* phrase stating
# a value/duration; these turn that phrase into a number IN CODE, so we only ever
# store a number that literally appears in the text (never one the model made up).

# A value phrase with an EXPLICIT unit, rupee prefix optional: "10.85 Crore",
# "Rs 47.38 Lakhs", "₹100 cr", "USD... " is ignored (no supported unit). We
# require the unit word — a bare number has no known scale and we never guess.
_VALUE_UNIT_RE = re.compile(
    r"(?:rs\.?|inr|₹)?\s*(\d[\d,]*(?:\.\d+)?)\s*"
    r"(crores?|cr|lakhs?|lacs?|millions?|mn|billions?|bn)\b",
    re.IGNORECASE,
)

# A plain rupee figure written NUMBER-FIRST with no "Rs" prefix, flagged as
# rupees by the classic "/-" suffix or a following "(Rupees ... only)" amount in
# words — e.g. "9,23,44,635/- (Rupees Nine Crore ...)". The ≥5-digit floor
# avoids grabbing small stray numbers. Converted as plain rupees (÷1,00,00,000).
_RUPEE_FIGURE_RE = re.compile(
    r"(\d[\d,]{4,}(?:\.\d+)?)\s*(?:/[-=]|\(?\s*rupees)",
    re.IGNORECASE,
)

# An amount in Indian digit grouping (x,xx,...,xxx — at least one lakh group),
# e.g. "9,30,00,000.00". That grouping is unmistakably a formatted rupee figure
# (Western thousands grouping is groups of 3), so we read it as rupees. Used only
# as a last resort, after the foreign-currency guard.
_INDIAN_NUMBER_RE = re.compile(r"(\d{1,2}(?:,\d{2}){1,},\d{3}(?:\.\d+)?)")

# Precise currency detection (word-boundaried, so "eur" doesn't match "Europe"
# nor "rs" match "years"). If a phrase names a foreign currency and no rupee
# marker, we keep it as text rather than mis-convert it as rupees.
_FOREIGN_CCY_RE = re.compile(
    r"[$€£¥]|\b(?:usd|eur|gbp|jpy|cny|rmb|aed|sgd|myr|sar|qar|kwd|omr|zar|aud|cad|"
    r"chf|dollars?|euros?|dirhams?|ringgit|yen)\b",
    re.IGNORECASE,
)
_INR_MARKER_RE = re.compile(
    r"₹|\brs\.?|\b(?:inr|rupees?|crores?|lakhs?|lacs?|cr)\b",
    re.IGNORECASE,
)


def value_phrase_to_crore(phrase: str | None) -> tuple[str | None, float | None]:
    """Normalize an order-value phrase (from the LLM) into crore.

    Tries the strict summary parser first (rupee-prefixed; also handles plain
    rupee amounts like "Rs. 36,95,760"), then a lenient match that accepts a
    number + an explicit unit without the prefix ("10.85 Crore"). Returns
    (matched_text, value_in_crore), or (None, None) when the phrase states no
    amount with a known unit — we never guess the scale of a bare number.
    """
    if not phrase:
        return None, None
    s = str(phrase).strip()
    if not s or s.casefold() == "not specified":
        return None, None
    text, crore = parse_value(s)  # strict: needs Rs/INR/₹ prefix
    if crore is not None:
        return text, crore
    # Guard: a foreign currency with no rupee/crore/lakh marker — don't convert
    # it as if it were rupees (that would be an ~80x error). Keep the phrase as
    # text, leave the number blank. crore/lakh are inherently INR, so their
    # presence means the amount is in rupees even if a stray "$" appears.
    # Foreign currency named with no rupee marker -> keep as text, don't convert
    # it as if it were rupees (that would be an ~80x error).
    if _FOREIGN_CCY_RE.search(s) and not _INR_MARKER_RE.search(s):
        return None, None
    # explicit unit without a prefix: "10.85 Crore", "50 million"
    m = _VALUE_UNIT_RE.search(s)
    if m:
        num = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        if unit.startswith(("crore", "cr")):
            crore = num
        elif unit.startswith(("lakh", "lac")):
            crore = num / 100
        elif unit.startswith(("million", "mn")):
            crore = num * 0.1
        elif unit.startswith(("billion", "bn")):
            crore = num * 100
        else:
            crore = None
        if crore is not None:
            return m.group(0).strip(), round(crore, 4)
    # plain rupee figure written number-first ("9,23,44,635/- (Rupees ...)")
    m2 = _RUPEE_FIGURE_RE.search(s)
    if m2:
        num = float(m2.group(1).replace(",", ""))
        return m2.group(0).strip(), round(num / 1e7, 4)
    # last resort: an Indian-grouped figure ("9,30,00,000.00") reads as rupees
    m3 = _INDIAN_NUMBER_RE.search(s)
    if m3:
        num = float(m3.group(1).replace(",", ""))
        return m3.group(1), round(num / 1e7, 4)
    return None, None


# A duration phrase: number + time unit ("24 months", "2 years", "18-month",
# "2.5 year period"). Years convert ×12.
# The number may itself be wrapped in parens ("(10) Months", "Five(05)Years"),
# and an optional (?:\([^)]*\)\s*)? swallows a spelled-out parenthetical between
# the number and the unit ("9(Nine) months", "12 (Twelve) months").
_DURATION_RE = re.compile(
    r"\(?(\d+(?:\.\d+)?)\)?\s*(?:\([^)]*\)\s*)?[-\s]?\s*"
    r"(years?|yrs?|months?|mons?|mos?|weeks?|days?)\b",
    re.IGNORECASE,
)
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
}


def duration_to_months(phrase: str | None) -> tuple[str | None, int | None]:
    """Normalize a duration phrase (from the LLM) into whole months.

    Handles "24 months", "2 years", "2.5 year", "18-month period" and a few
    spelled-out numbers ("two years"). Weeks/days are converted approximately.
    Returns (matched_text, months), or (None, None) when no duration is stated.
    A stated non-zero duration is floored at 1 month so it never rounds to 0.
    """
    if not phrase:
        return None, None
    s = str(phrase).strip()
    if not s or s.casefold() == "not specified":
        return None, None

    m = _DURATION_RE.search(s)
    if m:
        num = float(m.group(1))
        unit = m.group(2).lower()
        matched = m.group(0).strip()
    else:
        wm = re.search(
            r"\b(" + "|".join(_WORD_NUMBERS) + r")[-\s]+(years?|months?)\b",
            s,
            re.IGNORECASE,
        )
        if not wm:
            return None, None
        num = float(_WORD_NUMBERS[wm.group(1).lower()])
        unit = wm.group(2).lower()
        matched = wm.group(0).strip()

    if unit.startswith(("year", "yr")):
        months = num * 12
    elif unit.startswith(("month", "mon", "mo")):
        months = num
    elif unit.startswith("week"):
        months = num / 4.345
    elif unit.startswith("day"):
        months = num / 30.0
    else:
        return None, None
    months_int = int(round(months))
    if months_int <= 0:
        months_int = 1
    return matched, months_int


def parse_announcement(ann: dict[str, Any]) -> dict[str, Any]:
    """Map one BSE announcement row into `orders` columns.

    Uses the rich HEADLINE / MORE body text (what the BSE page shows) — not the
    boilerplate NEWSSUB title — and extracts the order value from it when stated.
    The remaining extracted fields (awarder, duration, industry) stay NULL for
    Steps 4-5.
    """
    scrip_code = _scrip_to_str(ann.get("SCRIP_CD"))
    summary = str(ann.get("HEADLINE") or "").strip()   # rich one-line body
    more = str(ann.get("MORE") or "").strip()           # expanded "Read more" body
    title = str(ann.get("NEWSSUB") or "").strip()       # boilerplate title
    headline = summary or title or None
    description = more or summary or title or None
    subcat = (str(ann.get("SUBCATNAME") or "")).strip() or None
    company = (str(ann.get("SLONGNAME") or "")).strip()
    if not company:
        company = f"BSE:{scrip_code}" if scrip_code else "Unknown company"
    newsid = ann.get("NEWSID")
    filed_at = to_iso8601(
        ann.get("NEWS_DT") or ann.get("DissemDT") or ann.get("News_submission_dt")
    )
    value_text, value_crore = parse_value(f"{summary} {more}")
    return {
        # identity
        "company_name": company,
        "bse_scrip_code": scrip_code,
        "nse_symbol": None,
        "isin": None,
        # value: from the summary when stated; else NULL -> filled from PDF (Steps 4-5)
        "order_value_text": value_text,
        "order_value_crore": value_crore,
        # still filled by Steps 4-5
        "awarder": None,
        "duration_text": None,
        "duration_months": None,
        "target_industry": None,
        "description": description,
        # evidence / provenance
        "exchange": "BSE",
        "category": subcat,
        "headline": headline,
        "attachment_url": build_attachment_url(ann.get("ATTACHMENTNAME")),
        "source_label": "BSE Filing",
        "raw_text": more or summary or None,
        "extraction_confidence": None,
        "extraction_model": None,
        # identity / dedup
        "bse_announcement_id": str(newsid).strip() if newsid is not None else None,
        "filed_at": filed_at,
    }


# --- fetching ----------------------------------------------------------------

def build_ann_url(page: int, day: datetime.date) -> str:
    """Build the announcements URL for one page of a SINGLE day, filtered to the
    order subcategory so BSE returns ONLY order wins (clean, no keyword noise)."""
    ymd = day.strftime("%Y%m%d")
    return (
        f"{BSE_ANN_API}?pageno={page}"
        f"&strCat={quote(ORDER_CATEGORY)}"
        f"&strPrevDate={ymd}&strScrip=&strSearch=P"
        f"&strToDate={ymd}&strType=C"
        f"&subcategory={quote(ORDER_SUBCATEGORY)}"
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
    """Build the ordered fetcher chain.

    Order: direct -> Scrape.do -> Firecrawl. BSE's announcements API serves
    datacenter IPs fine (the earlier blocks were a wrong endpoint), so a plain
    direct request is primary + free; the proxies are paid fallbacks in case a CI
    runner's IP is ever rate-limited (Scrape.do residential, Firecrawl in-page).
    """
    _session = requests.Session()

    def _via_direct(url: str) -> str:
        return _session.get(url, headers=BROWSER_HEADERS, timeout=timeout).text

    fetchers: list[Fetcher] = [("direct", _via_direct)]

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
            # Load BSE's page, then call the API from inside its JS context (like
            # the SPA) — correct Origin/Referer/cookies.
            return firecrawl.fetch_json_via_browser(BSE_SITE, url)

        fetchers.append(("firecrawl", _via_firecrawl))

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
        """Fetch all announcement rows for [from_date, to_date], ONE DAY AT A TIME
        (BSE only accepts single-day queries), paging within each day. `max_pages`
        is a global cap on page fetches to bound run time."""
        days = [
            to_date - datetime.timedelta(days=n)
            for n in range((to_date - from_date).days + 1)
        ]  # newest first
        probe = self._probe(build_ann_url(1, days[0]))
        if probe is None:
            return []
        name, fetch, first_page = probe
        self.source = name

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        remaining = self._max_pages

        def ingest(page_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            fresh = [r for r in page_rows if str(r.get("NEWSID")) not in seen]
            for r in fresh:
                seen.add(str(r.get("NEWSID")))
            rows.extend(fresh)
            return fresh

        for idx, day in enumerate(days):
            page = 1
            page_rows: list[dict[str, Any]] | None = first_page if idx == 0 else None
            while remaining > 0:
                if page_rows is None:
                    if page > 1:
                        time.sleep(self._page_delay)
                    try:
                        page_rows = parse_table(fetch(build_ann_url(page, day)))
                    except Exception as exc:  # noqa: BLE001
                        print(f"  [{name}] {day} page {page} error: {exc}")
                        break
                remaining -= 1
                if not page_rows:
                    break
                fresh = ingest(page_rows)
                total = page_rows[0].get("TotalPageCnt")
                if not fresh or (total and page >= int(total)):
                    break
                page += 1
                page_rows = None
            if remaining <= 0:
                print(f"  [reader] hit max_pages cap ({self._max_pages}); raise "
                      "INGEST_MAX_PAGES for more history")
                break

        print(f"  -> fetched {len(rows)} rows via {name} across {len(days)} day(s)")
        return rows


def iter_matched(
    announcements: Iterable[dict[str, Any]],
) -> Iterable[tuple[dict[str, Any], str, str | None]]:
    """Yield (parsed_order, rule, detail) for each order-matching announcement."""
    for ann in announcements:
        rule, detail = classify(ann)
        if rule is None:
            continue
        if is_noncommercial(ann):  # court/tribunal/insolvency order, not a win
            continue
        yield parse_announcement(ann), rule, detail
