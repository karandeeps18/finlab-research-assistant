"""Raw-layer storage for ingested filings.

Each filing lives under:
  data/raw/{ticker}/{accession_number}/
    ├── filing.html       (the actual document)
    └── metadata.json     (provenance: source URL, fetch time, form type, etc.)

The raw layer is IMMUTABLE — once written, never modified. Reprocessing
happens in downstream layers (parsed/, chunks/, embeddings/). This is the
Bronze/Silver/Gold pattern from data engineering, applied at small scale.

Idempotency: presence of metadata.json marks a filing as already-ingested.
Re-running the ingestor skips filings that already have metadata.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from finlab_research_assistant.core.config import settings
from finlab_research_assistant.core.logging import get_logger
from finlab_research_assistant.ingestion.models import Company, Filing

log = get_logger(__name__)


class RawStorage:
    """Manages the raw filing layer on disk.

    Filings are organized by ticker and accession number.
    All writes are atomic (write metadata.json at last so partial downloads will not look complete)
    """

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or settings.raw_dir

    def filing_dir(self, company: Company, filing: Filing) -> Path:
        """Path where a given filing lives."""
        return self._root / company.ticker / filing.accession_number

    def is_ingested(self, company: Company, filing: Filing) -> bool:
        """Check if filing has been fully ingested.
        
        Presence of metadata.json is our 'completion marker' - if missing - redownlaod 
        """
        metadata_path = self.filing_dir(company, filing) / "metadata.json"
        return metadata_path.exists()

    def write_filing(
        self,
        company: Company,
        filing: Filing,
        document_bytes: bytes,
        source_url: str,
    ) -> Path:
        """Write a filing + its metadata to disk atomically.

        Order matters: write the document first, metadata.json last.
        That way if we crash mid-write, the absence of metadata.json
        marks the filing as incomplete and we re-download on next run.
        """
        target_dir = self.filing_dir(company, filing)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Write the document
        doc_path = target_dir / "filing.html"
        doc_path.write_bytes(document_bytes)

        # provenance metadata
        metadata = {
            "company": {
                "cik": company.cik,
                "ticker": company.ticker,
                "name": company.name,
            },
            "filing": {
                "accession_number": filing.accession_number,
                "form_type": filing.form_type,
                "filing_date": filing.filing_date.isoformat(),
                "report_date": (
                    filing.report_date.isoformat() if filing.report_date else None
                ),
                "primary_document": filing.primary_document,
            },
            "ingestion": {
                "source_url": source_url,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "byte_count": len(document_bytes), 
            },
        }

        # write metadata.json 
        metadata_path = target_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))

        log.info(
            "filing.written",
            ticker=company.ticker,
            accession=filing.accession_number,
            bytes=len(document_bytes),
            path=str(target_dir),
        )
        return target_dir