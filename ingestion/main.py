"""Entrypoint for the orderbook ingestion pipeline.

For now this only performs a readiness check: it reports which configuration
keys are present (never their values) and exits cleanly. Real ingestion —
fetching BSE filings, parsing PDFs, extracting fields with OpenAI, and writing
rows to Cloudflare D1 — is wired up in later steps.
"""

from __future__ import annotations

from config import OPTIONAL_KEYS, REQUIRED_KEYS, Config


def main() -> int:
    config = Config.from_env()
    presence = config.presence()

    print("orderbook ingestion — readiness check")
    print("=" * 38)

    print("\nRequired secrets:")
    for key in REQUIRED_KEYS:
        mark = "✓ set    " if presence[key] else "✗ missing"
        print(f"  [{mark}] {key}")

    print("\nOptional secrets:")
    for key in OPTIONAL_KEYS:
        mark = "✓ set    " if presence[key] else "· unset  "
        print(f"  [{mark}] {key}")

    missing = config.missing_required()
    print()
    if missing:
        print(f"NOTE: {len(missing)} required secret(s) not set: {', '.join(missing)}")
        print("Real ingestion will need these before it can write to D1.")
    else:
        print("All required secrets present — ready to ingest (in a later step).")

    print("\nScaffold OK. No data was fetched or written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
