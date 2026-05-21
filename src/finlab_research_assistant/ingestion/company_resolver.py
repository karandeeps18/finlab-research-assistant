"""Resolve tickers to CIKs using SEC's company_tickers.json.

We fetch the file once and cache it on disk. It's small (~1 MB) and
updates infrequently. Re-fetching on every run is wasteful and slow.

This is the simplest possible caching pattern: file-on-disk with no
explicit TTL — refresh manually by deleting the cache file. For a real
production system you'd want a TTL (e.g., "re-fetch if older than 24h")
and probably push it into Redis or a CDN. For our project, file cache
is the right amount of engineering.
"""

from __future__ import annotations

import json
from pathlib import Path

from finlab_research_assistant.core.config import settings
from finlab_research_assistant.core.logging import get_logger
from finlab_research_assistant.ingestion.edgar_client import EdgarClient
from finlab_research_assistant.ingestion.models import Company

log = get_logger(__name__)


TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class CompanyResolver:
    """Resolves tickers to Company (CIK + name).

    Caches the ticker map on disk. Delete the cache file to force refresh.
    """

    def __init__(self, cache_path: Path | None = None) -> None:
        self._cache_path = (
            cache_path or settings.raw_dir / "_meta" / "company_tickers.json"
        )
        self._map: dict[str, Company] | None = None  # ticker (upper) → Company

    async def _load_or_fetch_map(self, client: EdgarClient) -> dict[str, Company]:
        """Load the ticker map from cache, or fetch+cache if missing."""
        if self._cache_path.exists():
            log.debug("ticker_map.cache_hit", path=str(self._cache_path))
            raw = json.loads(self._cache_path.read_text())
        else:
            log.info("ticker_map.fetching", url=TICKERS_URL)
            raw = await client.get_json(TICKERS_URL)
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(raw))
            log.info("ticker_map.cached", path=str(self._cache_path))

        # raw shape: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "..."}, ...}
        result: dict[str, Company] = {}
        for entry in raw.values():
            company = Company(
                cik=entry["cik_str"],  # validator will zero-pad
                ticker=entry["ticker"],
                name=entry["title"],
            )
            result[company.ticker.upper()] = company

        log.info("ticker_map.loaded", count=len(result))
        return result

    async def resolve(self, ticker: str, client: EdgarClient) -> Company:
        """Resolve a ticker to a Company. Raises KeyError if not found."""
        if self._map is None:
            self._map = await self._load_or_fetch_map(client)

        normalized = ticker.upper().strip()
        if normalized not in self._map:
            raise KeyError(f"Ticker not found in EDGAR ticker map: {ticker}")

        company = self._map[normalized]
        log.info(
            "ticker.resolved",
            ticker=normalized,
            cik=company.cik,
            name=company.name,
        )
        return company