"""Smoke test: resolve NVDA → CIK → list latest 10-K filing."""

import asyncio

from finlab_research_assistant.core.logging import configure_logging, get_logger
from finlab_research_assistant.ingestion.company_resolver import CompanyResolver
from finlab_research_assistant.ingestion.edgar_client import EdgarClient
from finlab_research_assistant.ingestion.filings_index import FilingsIndex

configure_logging("INFO")
log = get_logger(__name__)


async def main() -> None:
    ticker = "NVDA"

    async with EdgarClient() as client:
        # 1. Resolve ticker to company
        resolver = CompanyResolver()
        company = await resolver.resolve(ticker, client)

        # 2. Fetch filing history
        index = FilingsIndex()
        all_filings = await index.fetch_recent(company.cik, client)

        # 3. Find latest 10-K
        latest_10k = index.latest(all_filings, form_type="10-K")

        if latest_10k is None:
            log.error("no_10k_found", ticker=ticker)
            return

        log.info(
            "latest_10k.found",
            ticker=ticker,
            accession=latest_10k.accession_number,
            filing_date=str(latest_10k.filing_date),
            report_date=str(latest_10k.report_date),
            primary_doc=latest_10k.primary_document,
            url=latest_10k.document_url(company.cik),
        )


if __name__ == "__main__":
    asyncio.run(main())