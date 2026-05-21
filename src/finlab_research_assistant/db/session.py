from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from finlab_research_assistant.core.config import settings
from finlab_research_assistant.db.models import Base

# Module-level engine; one per process. SQLAlchemy pools connections internally.
engine = create_async_engine(
    settings.database_url,
    echo=False,  #for debugging set True to see all generated SQL
    future=True,
)

# Session factory bound to the engine
SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session, committing on success, rolling back on error."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables. For dev use only — production uses Alembic migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)