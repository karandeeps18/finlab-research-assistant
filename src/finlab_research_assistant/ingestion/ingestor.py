"""High-level ingestion orchestration.

Composes EdgarClient + CompanyResolver + FilingsIndex + RawStorage
into a single 'ingest these tickers' interface.
"""

from __future__ import annotations

from finlab_research_assistant.core.logging import get_logger
from finlab_research_assistant.ingestion.company_resolver import CompanyResolver
from finlab_research_assistant.ingestion.edgar_client import EdgarClient
from finlab_research_assistant.ingestion.filings_index import FilingsIndex
from finlab_research_assistant.ingestion.models import Company, Filing
from finlab_research_assistant.ingestion.storage import RawStorage

log = get_logger(__name__)


class Ingestor:
    """Orchestrates EDGAR ingestion end-to-end."""

    def __init__(
        self,
        resolver: CompanyResolver | None = None,
        index: FilingsIndex | None = None,
        storage: RawStorage | None = None,
    ) -> None:
        # Dependency injection 
        self._resolver = resolver or CompanyResolver()
        self._index = index or FilingsIndex()
        self._storage = storage or RawStorage()

    async def ingest_latest_filing(
        self,
        ticker: str,
        form_type: str = "10-K",
        client: EdgarClient | None = None,
    ) -> tuple[Company, Filing] | None:
        """Ingest the latest filing of a given form type for a ticker.

        Returns (company, filing) on success, None if no filing found.
        Idempotent — skips download if filing is already on disk.
        """
        # If no client passed, create one. Otherwise reuse the caller's
        # (so we can batch multiple ingestions sharing one connection pool).
        if client is None:
            async with EdgarClient() as new_client:
                return await self._ingest_with_client(
                    ticker, form_type, new_client
                )
        return await self._ingest_with_client(ticker, form_type, client)

    async def _ingest_with_client(
        self, ticker: str, form_type: str, client: EdgarClient
    ) -> tuple[Company, Filing] | None:
        # Resolve ticker → company
        company = await self._resolver.resolve(ticker, client)

        # Fetch filing history
        all_filings = await self._index.fetch_recent(company.cik, client)

        # Find latest of requested form type
        filing = self._index.latest(all_filings, form_type=form_type)
        if filing is None:
            log.warning(
                "no_filing_found", ticker=ticker, form_type=form_type
            )
            return None

        # Idempotency check; skip if already ingested
        if self._storage.is_ingested(company, filing):
            log.info(
                "filing.skipped_already_ingested",
                ticker=ticker,
                accession=filing.accession_number,
            )
            return company, filing

        # Download the document
        url = filing.document_url(company.cik)
        log.info("filing.downloading", url=url)
        document_bytes = await client.get_bytes(url)

        # Write to raw layer
        self._storage.write_filing(
            company=company,
            filing=filing,
            document_bytes=document_bytes,
            source_url=url,
        )

        return company, filing