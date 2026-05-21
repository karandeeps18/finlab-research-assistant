"""SQLAlchemy ORM models for metadata catalog.

Uses SQLAlchemy 2.0 declarative -> Mapped[] type-hint syntax.
All models inherit from Base; relationships are bidirectional where useful.

Why a DB instead of just walking the filesystem:
  - Indexed queries by ticker, form_type, date range
  - Joins between filings and downstream chunks/embeddings
  - Atomic transactions (write filing + its chunks together or roll back)
  - Standard schema migrations via Alembic as the model evolves
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass  # placeholder for forward refs


class Base(DeclarativeBase):
    """Shared base for all ORM models."""


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    cik: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(255))

    # One-to-many: a company has many filings
    filings: Mapped[list["Filing"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Company {self.ticker} (CIK {self.cik})>"


class Filing(Base):
    __tablename__ = "filings"
    __table_args__ = (
        # Accession number is globally unique across all of EDGAR,
        # but we add the composite constraint for safety + clarity.
        UniqueConstraint("company_id", "accession_number", name="uq_filing"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), index=True
    )

    accession_number: Mapped[str] = mapped_column(
        String(25), unique=True, index=True
    )
    form_type: Mapped[str] = mapped_column(String(20), index=True)
    filing_date: Mapped[date] = mapped_column(index=True)
    report_date: Mapped[date | None] = mapped_column(nullable=True)
    primary_document: Mapped[str] = mapped_column(String(255))

    # Provenance
    raw_path: Mapped[str] = mapped_column(String(500))  # filesystem path
    ingested_at: Mapped[datetime]

    # Reverse relationships
    company: Mapped[Company] = relationship(back_populates="filings")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="filing",
        cascade="all, delete-orphan",)

    def __repr__(self) -> str:
        return f"<Filing {self.form_type} {self.accession_number}>"
    
class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(
        ForeignKey("filings.id"), index=True
    )

    chunk_index: Mapped[int]
    section_id: Mapped[str] = mapped_column(String(50), index=True)
    section_label: Mapped[str] = mapped_column(String(50), index=True)
    section_title: Mapped[str] = mapped_column(String(500))
    text: Mapped[str]
    char_start: Mapped[int]
    char_end: Mapped[int]
    token_count: Mapped[int]
    priority: Mapped[float]

    filing: Mapped["Filing"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk #{self.chunk_index} {self.section_label}>"
