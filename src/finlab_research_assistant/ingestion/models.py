"""Pydantic models for EDGAR API responses.

These are 'schema at the boundary' types — we parse raw EDGAR JSON into
these at the moment of HTTP response, and the rest of the codebase only
ever sees typed objects. If EDGAR changes their schema, exactly one
place breaks: the parser, loudly, at startup.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class Company(BaseModel):
    """A public company, identified by CIK + ticker."""

    cik: Annotated[str, Field(min_length=10, max_length=10)]  # zero-padded
    ticker: str
    name: str

    @field_validator("cik", mode="before")
    @classmethod
    def pad_cik(cls, v: str | int) -> str:
        """EDGAR CIKs are 1-10 digit integers; we always store padded to 10."""
        return str(v).zfill(10)


class Filing(BaseModel):
    """A single filing in a company's submission history."""

    accession_number: str  # e.g. "0001045810-25-000023" — globally unique
    form_type: str  # "10-K", "10-Q", "8-K", "13F", etc.
    filing_date: date
    report_date: date | None = None  # period the filing covers
    primary_document: str  # e.g. "nvda-20250126.htm"
    primary_doc_description: str | None = None

    @property
    def accession_no_dashes(self) -> str:
        """Accession number without dashes — used in URL paths."""
        return self.accession_number.replace("-", "")

    def document_url(self, cik: str) -> str:
        """Build the URL to the primary filing document.

        EDGAR archive URLs follow this pattern:
          https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{primary_document}

        Note: the CIK in the URL path is the integer form (no leading zeros).
        """
        cik_int = str(int(cik))  # strip leading zeros
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_int}/{self.accession_no_dashes}/{self.primary_document}"
        )