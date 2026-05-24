"""End-to-end smoke test with DB persistence.

Initializes the database, runs ingestion also writes metadata
to the DB, then queries the DB to confirm everything is wired correctly.
"""

import asyncio

from sqlalchemy import select

from finlab_research_assistant.core.logging import configure_logging, get_logger
from finlab_research_assistant.db.models import Company, Filing
from finlab_research_assistant.db.session import get_session, init_db
from finlab_research_assistant.ingestion.edgar_client import EdgarClient
from finlab_research_assistant.ingestion.ingestor import Ingestor

configure_logging("INFO")
log = get_logger(__name__)


async def main() -> None:
    
    # Create tables
    await init_db()
    log.info("db.initialized")

    # Run ingestion
    ingestor = Ingestor()
    async with EdgarClient() as client:
        for ticker in ["NVDA", "MSFT"]:
            await ingestor.ingest_latest_filing(
                ticker=ticker, form_type="10-K", client=client
            )

    # Query the DB to verify
    async with get_session() as session:
        result = await session.execute(
            select(Filing, Company)
            .join(Company)
            .where(Filing.form_type == "10-K")
            .order_by(Filing.filing_date.desc())
        )
        for filing, company in result.all():
            log.info(
                "db.row",
                ticker=company.ticker,
                accession=filing.accession_number,
                filing_date=str(filing.filing_date),
            )


if __name__ == "__main__":
    asyncio.run(main())