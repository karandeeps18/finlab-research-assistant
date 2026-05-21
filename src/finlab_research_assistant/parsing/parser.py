from __future__ import annotations

import re
from pathlib import Path

from unstructured.partition.html import partition_html

from finlab_research_assistant.core.logging import get_logger
from finlab_research_assistant.parsing.models import ParsedFiling, ParsedSection

log = get_logger(__name__)


# 10-K section markers — case-insensitive, allow flexible whitespace
# Matches "Item 1.", "ITEM 1A.", "Item 7A.", etc.
SECTION_PATTERN = re.compile(
    r"^\s*(Item\s+(\d+[A-Z]?))\s*\.?\s*([^\n]{0,200})",
    re.IGNORECASE | re.MULTILINE,
)


class FilingParser:
    """Parses raw 10-K HTML into structured sections."""

    def parse(
        self, raw_html_path: Path, ticker: str, accession_number: str
    ) -> ParsedFiling:
        """Parse a 10-K HTML file."""
        log.info("parser.start", path=str(raw_html_path))

        # 1. Extract clean text via unstructured (handles layout, strips boilerplate)
        elements = partition_html(filename=str(raw_html_path))
        full_text = "\n\n".join(str(el) for el in elements if str(el).strip())
        log.info(
            "parser.text_extracted",
            char_count=len(full_text),
            element_count=len(elements),
        )

        # 2. Find section boundaries via regex
        sections = self._extract_sections(full_text)
        log.info("parser.sections_found", count=len(sections))

        return ParsedFiling(
            accession_number=accession_number,
            ticker=ticker,
            sections=sections,
            full_text=full_text,
            char_count=len(full_text),
        )

    def _extract_sections(self, text: str) -> list[ParsedSection]:
        """Find Item N / Item NA section boundaries."""
        matches = list(SECTION_PATTERN.finditer(text))

        if not matches:
            # Fallback — return whole doc as one section
            log.warning("parser.no_sections_detected")
            return [
                ParsedSection(
                    section_id="full_document",
                    title="Full Document",
                    text=text,
                    char_start=0,
                    char_end=len(text),
                )
            ]

        sections: list[ParsedSection] = []
        for i, match in enumerate(matches):
            item_num = match.group(2).lower()
            title_remainder = match.group(3).strip()
            title = f"Item {item_num.upper()}. {title_remainder}".strip(". ")

            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

            section_text = text[start:end].strip()

            # Skip tiny sections (likely table-of-contents references)
            if len(section_text) < 200:
                continue

            sections.append(
                ParsedSection(
                    section_id=f"item_{item_num}",
                    title=title,
                    text=section_text,
                    char_start=start,
                    char_end=end,
                )
            )

        # Dedupe by section_id (TOC + actual section often both detected)
        # Keep the LARGEST occurrence of each section_id
        by_id: dict[str, ParsedSection] = {}
        for s in sections:
            existing = by_id.get(s.section_id)
            if existing is None or len(s.text) > len(existing.text):
                by_id[s.section_id] = s

        return sorted(by_id.values(), key=lambda s: s.char_start)