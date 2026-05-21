"""End-to-end smoke test: ingest the latest 10-K for NVDA.
"""

import asyncio

from finlab_research_assistant.core.logging import configure_logging, get_logger
from finlab_research_assistant.ingestion.edgar_client import EdgarClient
from finlab_research_assistant.ingestion.ingestor import Ingestor

configure_logging("INFO")
log = get_logger(__name__)


async def main() -> None:
    ingestor = Ingestor()

    async with EdgarClient() as client:
        result = await ingestor.ingest_latest_filing(
            ticker="NVDA", form_type="10-K", client=client
        )

    if result is None:
        log.error("ingestion.failed")
        return

    company, filing = result
    log.info(
        "ingestion.complete",
        ticker=company.ticker,
        accession=filing.accession_number,
        filing_date=str(filing.filing_date),
    )


if __name__ == "__main__":
    asyncio.run(main())