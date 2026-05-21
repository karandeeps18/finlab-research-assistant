"""High-level ingestion orchestration.

Composes EdgarClient + CompanyResolver + FilingsIndex + RawStorage
into a single 'ingest these tickers' interface, syncing both the
raw filesystem layer and the metadata DB.
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

        Idempotent — skips download if filing is already on disk,
        but still syncs to DB so the catalog is always consistent.
        """
        if client is None:
            async with EdgarClient() as new_client:
                return await self._ingest_with_client(
                    ticker, form_type, new_client
                )
        return await self._ingest_with_client(ticker, form_type, client)

    async def _ingest_with_client(
        self, ticker: str, form_type: str, client: EdgarClient
    ) -> tuple[Company, Filing] | None:
        #  Resolve ticker → company
        company = await self._resolver.resolve(ticker, client)

        # Fetch filing history
        all_filings = await self._index.fetch_recent(company.cik, client)

        #  Find latest of requested form type
        filing = self._index.latest(all_filings, form_type=form_type)
        if filing is None:
            log.warning("no_filing_found", ticker=ticker, form_type=form_type)
            return None

        #  Idempotency check; skip download but STILL sync to DB
        if self._storage.is_ingested(company, filing):
            log.info(
                "filing.skipped_already_ingested",
                ticker=ticker,
                accession=filing.accession_number,
            )
            await self._sync_to_db(company, filing)
            return company, filing

        # Download
        url = filing.document_url(company.cik)
        log.info("filing.downloading", url=url)
        document_bytes = await client.get_bytes(url)

        # Write to raw layer
        target_dir = self._storage.write_filing(
            company=company,
            filing=filing,
            document_bytes=document_bytes,
            source_url=url,
        )

        # Persist to DB
        await self._sync_to_db(company, filing, raw_path=str(target_dir))

        return company, filing

    async def _sync_to_db(
        self,
        company: Company,
        filing: Filing,
        raw_path: str | None = None,
    ) -> None:
        """Upsert company and filing into the metadata DB."""
        from finlab_research_assistant.db.repository import (
            upsert_company,
            upsert_filing,
        )
        from finlab_research_assistant.db.session import get_session

        log.info(
            "db_sync.start",
            ticker=company.ticker,
            accession=filing.accession_number,
        )

        if raw_path is None:
            raw_path = str(self._storage.filing_dir(company, filing))

        try:
            async with get_session() as session:
                db_company = await upsert_company(session, company)
                await upsert_filing(session, db_company, filing, raw_path)
            log.info("db_sync.complete")
        except Exception as e:
            log.error(
                "db_sync.failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise