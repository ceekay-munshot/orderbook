"""Configuration for the orderbook ingestion pipeline.

Settings come from environment variables. In CI (GitHub Actions) they are
provided as GitHub Secrets; for local development they can live in a `.env`
file at the repo root (or in `ingestion/`), which is loaded automatically if
`python-dotenv` is installed.

IMPORTANT: never log or print secret *values* — only whether a key is present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # python-dotenv is optional; in CI the env vars are supplied directly.
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True))
except ImportError:  # pragma: no cover - only hit when dotenv isn't installed
    pass


# Required secrets — the pipeline needs all of these to actually run.
REQUIRED_KEYS: tuple[str, ...] = (
    "OPENAI_API_KEY",       # field extraction
    "FIRECRAWL_API_KEY",    # page / PDF fetch + parse
    "SCRAPEDO_API_KEY",     # proxied fetch for BSE
    "CF_ACCOUNT_ID",        # Cloudflare account (D1 write target)
    "CF_D1_DATABASE_ID",    # Cloudflare D1 database id
    "CF_API_TOKEN",         # Cloudflare API token
)

# Optional secrets — nice to have, not required for a run.
OPTIONAL_KEYS: tuple[str, ...] = (
    "SCREENER_EMAIL",       # screener.in login (optional)
    "SCREENER_PASSWORD",    # screener.in login (optional)
    "MUNS_TOKEN",           # internal token (optional)
)

ALL_KEYS: tuple[str, ...] = REQUIRED_KEYS + OPTIONAL_KEYS


@dataclass(frozen=True)
class Config:
    """Typed snapshot of the pipeline configuration.

    Values may be ``None`` when a key is unset. Use :meth:`missing_required`
    to check readiness before doing real work.
    """

    openai_api_key: str | None
    firecrawl_api_key: str | None
    scrapedo_api_key: str | None
    cf_account_id: str | None
    cf_d1_database_id: str | None
    cf_api_token: str | None
    screener_email: str | None
    screener_password: str | None
    muns_token: str | None

    @classmethod
    def from_env(cls) -> "Config":
        """Build a Config from the current process environment."""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"),
            scrapedo_api_key=os.getenv("SCRAPEDO_API_KEY"),
            cf_account_id=os.getenv("CF_ACCOUNT_ID"),
            cf_d1_database_id=os.getenv("CF_D1_DATABASE_ID"),
            cf_api_token=os.getenv("CF_API_TOKEN"),
            screener_email=os.getenv("SCREENER_EMAIL"),
            screener_password=os.getenv("SCREENER_PASSWORD"),
            muns_token=os.getenv("MUNS_TOKEN"),
        )

    def presence(self) -> dict[str, bool]:
        """Map every known key -> whether it is set. Never returns values."""
        return {key: bool(os.getenv(key)) for key in ALL_KEYS}

    def missing_required(self) -> list[str]:
        """List required keys that are not set."""
        return [key for key in REQUIRED_KEYS if not os.getenv(key)]
