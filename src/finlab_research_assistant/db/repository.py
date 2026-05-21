from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from finlab_research_assistant.core.logging import get_logger
from finlab_research_assistant.db.models import Company, Filing
from finlab_research_assistant.ingestion.models import Company as CompanyDTO
from finlab_research_assistant.ingestion.models import Filing as FilingDTO
from finlab_research_assistant.db.models import Chunk as ChunkORM


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

async def persist_chunks(
    session: AsyncSession,
    filing: Filing,
    chunks: list,  # list[Chunk DTO from chunking module]
) -> int:
    """Persist chunks to DB. Idempotent — deletes prior chunks for this
    filing first so reprocessing replaces cleanly."""
    # Clear any existing chunks for this filing
    await session.execute(
        delete(ChunkORM).where(ChunkORM.filing_id == filing.id)
    )

    orm_chunks = [
        ChunkORM(
            filing_id=filing.id,
            chunk_index=c.chunk_index,
            section_id=c.section_id,
            section_label=c.section_label,
            section_title=c.section_title,
            text=c.text,
            char_start=c.char_start,
            char_end=c.char_end,
            token_count=c.token_count,
            priority=c.priority,
        )
        for c in chunks
    ]
    session.add_all(orm_chunks)
    await session.flush()
    log.info(
        "chunks.persisted",
        filing_id=filing.id,
        count=len(orm_chunks),
    )
    return len(orm_chunks)
