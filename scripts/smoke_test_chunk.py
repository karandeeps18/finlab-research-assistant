"""Smoke test: parse + section-aware chunk + persist NVDA.

Verifies that:
  - The section taxonomy includes Risk Factors, MD&A, Business
  - Skip-list correctly drops Properties, Mine Safety, etc.
  - Priority weighting is applied (1.5 for Risk Factors / MD&A)
  - Chunks are queryable by section_label for retrieval-time filtering
"""

import asyncio
from collections import Counter

from sqlalchemy import func, select

from finlab_research_assistant.chunking.chunker import SectionAwareChunker
from finlab_research_assistant.core.config import settings
from finlab_research_assistant.core.logging import configure_logging, get_logger
from finlab_research_assistant.db.models import Chunk as ChunkORM
from finlab_research_assistant.db.models import Filing
from finlab_research_assistant.db.repository import persist_chunks
from finlab_research_assistant.db.session import get_session, init_db
from finlab_research_assistant.ingestion.edgar_client import EdgarClient
from finlab_research_assistant.ingestion.ingestor import Ingestor
from finlab_research_assistant.parsing.parser import FilingParser

configure_logging("INFO")
log = get_logger(__name__)


async def main() -> None:
    # Ensure DB schema is current
    await init_db()

    # Re-sync NVDA filing metadata to DB (in case finlab.db was deleted)
    ingestor = Ingestor()
    async with EdgarClient() as client:
        await ingestor.ingest_latest_filing("NVDA", "10-K", client)

    # Parse the NVDA 10-K
    nvda_dir = next((settings.raw_dir / "NVDA").iterdir())
    parser = FilingParser()
    parsed = parser.parse(
        raw_html_path=nvda_dir / "filing.html",
        ticker="NVDA",
        accession_number=nvda_dir.name,
    )

    # Chunk with section taxonomy
    chunker = SectionAwareChunker()
    chunks = chunker.chunk_filing(parsed)

    # Persist chunks
    async with get_session() as session:
        result = await session.execute(
            select(Filing).where(Filing.accession_number == nvda_dir.name)
        )
        filing = result.scalar_one()
        await persist_chunks(session, filing, chunks)

    # Stats: how did the taxonomy partition the filing?
    by_label = Counter(c.section_label for c in chunks)
    log.info("chunks.by_label", distribution=dict(by_label))

    # Verify in DB; group by label and priority
    async with get_session() as session:
        result = await session.execute(
            select(
                ChunkORM.section_label,
                ChunkORM.priority,
                func.count(ChunkORM.id).label("count"),
                func.sum(ChunkORM.token_count).label("total_tokens"),
            )
            .group_by(ChunkORM.section_label, ChunkORM.priority)
            .order_by(ChunkORM.priority.desc())
        )
        log.info("=== Priority Summary ===")
        for row in result.all():
            log.info(
                "priority.row",
                label=row.section_label,
                priority=row.priority,
                chunks=row.count,
                total_tokens=row.total_tokens,
            )

        # Show a sample Risk Factors chunk to verify content
        result = await session.execute(
            select(ChunkORM)
            .where(ChunkORM.section_label == "risk_factors")
            .limit(1)
        )
        sample = result.scalar_one_or_none()
        if sample:
            log.info(
                "sample_chunk",
                section=sample.section_id,
                label=sample.section_label,
                tokens=sample.token_count,
                preview=sample.text[:200],
            )


if __name__ == "__main__":
    asyncio.run(main())