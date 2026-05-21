"""Fetch a company's filing history from EDGAR's submissions endpoint.

Endpoint pattern:
  https://data.sec.gov/submissions/CIK{padded_cik}.json

Response shape (abridged):
  {
    "cik": "1045810",
    "name": "NVIDIA CORP",
    "tickers": ["NVDA"],
    "filings": {
      "recent": {
        "accessionNumber": ["0001045810-25-000023", ...],
        "form": ["10-K", "10-Q", ...],
        "filingDate": ["2025-02-21", ...],
        "reportDate": ["2025-01-26", ...],
        "primaryDocument": ["nvda-20250126.htm", ...],
        ...
      }
    }
  }

The `recent` block is a "columnar" structure — arrays of equal length where
index i across all arrays describes filing i. We transpose this to a list
of Filing objects for ergonomic downstream use.
"""

from __future__ import annotations

from finlab_research_assistant.core.logging import get_logger
from finlab_research_assistant.ingestion.edgar_client import EdgarClient
from finlab_research_assistant.ingestion.models import Filing

log = get_logger(__name__)


SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik}.json"


class FilingsIndex:
    """Fetches and parses a company's recent filing history."""

    async def fetch_recent(
        self, cik: str, client: EdgarClient
    ) -> list[Filing]:
        """Fetch the 'recent' filings block for a company.

        Returns a list of Filing objects sorted newest-first (EDGAR's order).
        """
        url = SUBMISSIONS_URL_TEMPLATE.format(cik=cik)
        log.info("filings_index.fetching", cik=cik, url=url)

        data = await client.get_json(url)
        recent = data["filings"]["recent"]

        # Transpose columnar arrays → list of Filing objects.
        # Every array has the same length; index i across all arrays describes filing i.
        accession_numbers = recent["accessionNumber"]
        forms = recent["form"]
        filing_dates = recent["filingDate"]
        report_dates = recent.get("reportDate", [None] * len(accession_numbers))
        primary_docs = recent["primaryDocument"]
        primary_descs = recent.get(
            "primaryDocDescription", [None] * len(accession_numbers)
        )

        filings: list[Filing] = []
        for i in range(len(accession_numbers)):
            filings.append(
                Filing(
                    accession_number=accession_numbers[i],
                    form_type=forms[i],
                    filing_date=filing_dates[i],  # pydantic parses ISO date string
                    report_date=report_dates[i] if report_dates[i] else None,
                    primary_document=primary_docs[i],
                    primary_doc_description=primary_descs[i],
                )
            )

        log.info("filings_index.fetched", cik=cik, count=len(filings))
        return filings

    def filter_by_form(
        self, filings: list[Filing], form_type: str
    ) -> list[Filing]:
        """Filter to a specific form type, e.g., '10-K'."""
        return [f for f in filings if f.form_type == form_type]

    def latest(
        self, filings: list[Filing], form_type: str | None = None
    ) -> Filing | None:
        """Return the most recent filing, optionally filtered by form type.

        Returns None if no matching filing found.
        """
        candidates = (
            self.filter_by_form(filings, form_type) if form_type else filings
        )
        if not candidates:
            return None
        # EDGAR returns newest-first, but be defensive — sort explicitly.
        return max(candidates, key=lambda f: f.filing_date)