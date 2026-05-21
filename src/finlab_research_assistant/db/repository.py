from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finlab_research_assistant.core.logging import get_logger
from finlab_research_assistant.db.models import Company, Filing
from finlab_research_assistant.ingestion.models import Company as CompanyDTO
from finlab_research_assistant.ingestion.models import Filing as FilingDTO

log = get_logger(__name__)


async def upsert_company(session: AsyncSession, dto: CompanyDTO) -> Company:
    """Insert or fetch a company by CIK."""
    result = await session.execute(
        select(Company).where(Company.cik == dto.cik)
    )
    company = result.scalar_one_or_none()

    if company is None:
        company = Company(cik=dto.cik, ticker=dto.ticker, name=dto.name)
        session.add(company)
        await session.flush()  # populates company.id without committing
        log.info("company.created", ticker=dto.ticker, cik=dto.cik)
    else:
        log.debug("company.exists", ticker=dto.ticker, cik=dto.cik)

    return company


async def upsert_filing(
    session: AsyncSession,
    company: Company,
    dto: FilingDTO,
    raw_path: str,
) -> Filing:
    """Insert a filing record if not already present."""
    result = await session.execute(
        select(Filing).where(Filing.accession_number == dto.accession_number)
    )
    filing = result.scalar_one_or_none()

    if filing is None:
        filing = Filing(
            company_id=company.id,
            accession_number=dto.accession_number,
            form_type=dto.form_type,
            filing_date=dto.filing_date,
            report_date=dto.report_date,
            primary_document=dto.primary_document,
            raw_path=raw_path,
            ingested_at=datetime.now(timezone.utc),
        )
        session.add(filing)
        await session.flush()
        log.info(
            "filing.persisted",
            accession=dto.accession_number,
            form=dto.form_type,
        )
    else:
        log.debug("filing.exists", accession=dto.accession_number)

    return filing