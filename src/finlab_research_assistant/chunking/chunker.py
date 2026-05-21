"""Section-aware chunker for 10-K filings.

Strategy:
  - Whitelist sections that matter for investment research (skip Properties,
    Mine Safety, etc.)
  - Apply per-section chunk sizing — dense sections (Risk Factors, MD&A)
    get smaller chunks for retrieval precision
  - Tag each chunk with section_id + section_label + priority + provenance
  - Section metadata enables:
      (a) pre-filtering at retrieval ("only Risk Factors for NVDA FY2026")
      (b) precise citations ("Item 1A, chunk 7, chars 12000-13000")
      (c) priority weighting in hybrid retrieval scoring

Tradeoff: rule-based section weights are fragile (10-K structure evolves
across companies and years). A learned classifier on past filings would
be more robust at scale. We stay rule-based for clarity and auditability.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from finlab_research_assistant.core.logging import get_logger
from finlab_research_assistant.parsing.models import ParsedFiling, ParsedSection

log = get_logger(__name__)


# Section taxonomy for 10-K filings.
# - "include": whether to chunk this section at all
# - "priority": retrieval boost (1.0 = baseline, >1.0 = boost)
# - "chunk_size": dense sections get smaller chunks for precision
# - "label": human-friendly category used in retrieval filtering
SECTION_TAXONOMY: dict[str, dict[str, Any]] = {
    # Investment-critical sections — small chunks, high priority
    "item_1a": {"include": True, "priority": 1.5, "chunk_size": 800,
                "label": "risk_factors"},
    "item_7":  {"include": True, "priority": 1.5, "chunk_size": 800,
                "label": "mdna"},
    "item_7a": {"include": True, "priority": 1.3, "chunk_size": 800,
                "label": "market_risk"},

    # Business context — medium chunks, elevated priority
    "item_1":  {"include": True, "priority": 1.2, "chunk_size": 1000,
                "label": "business"},
    "item_8":  {"include": True, "priority": 1.0, "chunk_size": 1200,
                "label": "financials"},
    "item_9a": {"include": True, "priority": 1.0, "chunk_size": 1000,
                "label": "controls"},

    # Governance — medium chunks, lower priority
    "item_10": {"include": True, "priority": 0.8, "chunk_size": 1000,
                "label": "governance"},
    "item_11": {"include": True, "priority": 0.8, "chunk_size": 1000,
                "label": "compensation"},
    "item_13": {"include": True, "priority": 0.8, "chunk_size": 1000,
                "label": "related_party"},
    "item_5":  {"include": True, "priority": 0.9, "chunk_size": 1000,
                "label": "market_for_equity"},

    # Skip these — low signal for investment research
    "item_2":  {"include": False},   # Properties
    "item_3":  {"include": False},   # Legal Proceedings (usually in 1A)
    "item_4":  {"include": False},   # Mine Safety
    "item_9":  {"include": False},   # Changes in Accountants
    "item_9c": {"include": False},   # Foreign Jurisdictions
    "item_15": {"include": False},   # Exhibits

    # Fallback for unknown / new sections
    "_default": {"include": True, "priority": 1.0, "chunk_size": 1000,
                 "label": "other"},
}


class Chunk(BaseModel):
    """A chunk with full provenance + retrieval metadata."""

    # Identity
    chunk_index: int
    accession_number: str
    ticker: str

    # Section metadata: drives filtering and citation
    section_id: str            # "item_1a"
    section_label: str         # "risk_factors"
    section_title: str         # full human title

    # Content
    text: str
    char_start: int
    char_end: int
    token_count: int

    # Retrieval hint
    priority: float            # boost factor for ranking


class SectionAwareChunker:
    """Whitelist-aware chunker with per-section sizing and priority tagging."""

    def __init__(
        self,
        default_overlap: int = 200,
        min_chunk_size: int = 200,
    ) -> None:
        self._overlap = default_overlap
        self._min = min_chunk_size

    def chunk_filing(self, parsed: ParsedFiling) -> list[Chunk]:
        """Produce chunks for a parsed filing, applying section taxonomy."""
        chunks: list[Chunk] = []
        idx = 0
        skipped: list[str] = []

        for section in parsed.sections:
            taxonomy = SECTION_TAXONOMY.get(
                section.section_id, SECTION_TAXONOMY["_default"]
            )

            if not taxonomy.get("include", True):
                skipped.append(section.section_id)
                continue

            section_chunks = self._chunk_section(
                section=section,
                parsed=parsed,
                taxonomy=taxonomy,
                start_index=idx,
            )
            chunks.extend(section_chunks)
            idx += len(section_chunks)

        log.info(
            "chunker.complete",
            accession=parsed.accession_number,
            ticker=parsed.ticker,
            chunks=len(chunks),
            sections_included=len({c.section_id for c in chunks}),
            sections_skipped=skipped,
        )
        return chunks

    def _chunk_section(
        self,
        section: ParsedSection,
        parsed: ParsedFiling,
        taxonomy: dict[str, Any],
        start_index: int,
    ) -> list[Chunk]:
        """Chunk a single section using its taxonomy-specified size."""
        chunk_size: int = taxonomy["chunk_size"]
        priority: float = taxonomy["priority"]
        label: str = taxonomy.get("label", "other")
        text = section.text

        # Short section: single chunk
        if len(text) <= chunk_size:
            if len(text.strip()) < self._min:
                return []
            return [
                self._make_chunk(
                    chunk_index=start_index,
                    section=section,
                    parsed=parsed,
                    label=label,
                    priority=priority,
                    text=text.strip(),
                    local_start=0,
                    local_end=len(text),
                )
            ]

        # Long section: overlapping chunks with sentence-aware breaks
        chunks: list[Chunk] = []
        local_start = 0
        chunk_idx = start_index

        while local_start < len(text):
            local_end = min(local_start + chunk_size, len(text))
            chunk_text = text[local_start:local_end]

            # Try to break on a sentence/paragraph boundary near the tail
            if local_end < len(text):
                tail = chunk_text[-200:]
                break_offset = max(tail.rfind("\n\n"), tail.rfind(". "))
                if break_offset > 0:
                    chunk_text = chunk_text[: -(200 - break_offset)]
                    local_end = local_start + len(chunk_text)

            if len(chunk_text.strip()) >= self._min:
                chunks.append(
                    self._make_chunk(
                        chunk_index=chunk_idx,
                        section=section,
                        parsed=parsed,
                        label=label,
                        priority=priority,
                        text=chunk_text.strip(),
                        local_start=local_start,
                        local_end=local_end,
                    )
                )
                chunk_idx += 1

            local_start = local_end - self._overlap
            if local_start <= 0 or local_end >= len(text):
                break

        return chunks

    def _make_chunk(
        self,
        chunk_index: int,
        section: ParsedSection,
        parsed: ParsedFiling,
        label: str,
        priority: float,
        text: str,
        local_start: int,
        local_end: int,
    ) -> Chunk:
        """Construct a Chunk DTO with full provenance."""
        return Chunk(
            chunk_index=chunk_index,
            accession_number=parsed.accession_number,
            ticker=parsed.ticker,
            section_id=section.section_id,
            section_label=label,
            section_title=section.title,
            text=text,
            char_start=section.char_start + local_start,
            char_end=section.char_start + local_end,
            token_count=len(text) // 4,
            priority=priority,
        )