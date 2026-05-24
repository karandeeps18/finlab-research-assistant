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

# Financial-statement headings, these don't follow the Item-N convention
# but logically belong to Item 8. We detect them in a second pass.
FINANCIAL_STATEMENT_PATTERN = re.compile(
    r"^\s*(CONSOLIDATED\s+(?:"
    r"BALANCE\s+SHEETS?"
    r"|STATEMENTS?\s+OF\s+(?:"
    r"OPERATIONS"
    r"|INCOME"
    r"|COMPREHENSIVE\s+(?:INCOME|LOSS)"
    r"|CASH\s+FLOWS?"
    r"|STOCKHOLDERS.?\s+EQUITY"
    r"|SHAREHOLDERS.?\s+EQUITY"
    r"|CHANGES\s+IN\s+STOCKHOLDERS.?\s+EQUITY"
    r")"
    r")|NOTES\s+TO\s+(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS?)",
    re.IGNORECASE | re.MULTILINE,
)


class FilingParser:
    """Parses raw 10-K HTML into structured sections."""

    def parse(
        self, raw_html_path: Path, ticker: str, accession_number: str
    ) -> ParsedFiling:
        """Parse a 10-K HTML file into structured sections.

        Two-pass parsing:
          Pass 1: Item-N pattern detection for narrative sections (Item 1, 1A, 7, etc.)
          Pass 2: Financial-statement heading detection — folds these under item_8
                  so retrieval finds them under the financials label

        The second pass exists because the actual financial statements rarely sit
        under an 'Item 8' heading in the HTML — they live under their own headings
        like 'CONSOLIDATED STATEMENTS OF OPERATIONS'. Without this pass, queries
        like 'what was NVDA gross margin' can never retrieve the income statement.
        """
        log.info("parser.start", path=str(raw_html_path))

        elements = partition_html(filename=str(raw_html_path))
        full_text = "\n\n".join(str(el) for el in elements if str(el).strip())
        log.info(
            "parser.text_extracted",
            char_count=len(full_text),
            element_count=len(elements),
        )

        # Pass 1: Item-N sections (narrative + cross-referenced sections)
        sections = self._extract_sections(full_text)
        log.info("parser.item_sections_found", count=len(sections))

        # Pass 2: Financial-statement sections (fold under item_8)
        # financial_sections = self._extract_financial_statements(full_text, sections)
        # if financial_sections:
        #     # Merge with the existing item_8 (if any) by aggregating text
        #     sections = self._merge_financial_into_item_8(sections, financial_sections)
        #     log.info(
        #         "parser.financial_statements_merged",
        #         count=len(financial_sections),
        #     )

        log.info("parser.sections_found", count=len(sections))

        return ParsedFiling(
            accession_number=accession_number,
            ticker=ticker,
            sections=sections,
            full_text=full_text,
            char_count=len(full_text),
        )

    # def _extract_financial_statements(
    #     self,
    #     text: str,
    #     item_sections: list[ParsedSection],
    # ) -> list[ParsedSection]:
    #     """Find financial-statement headings and capture their content.

    #     Returns a list of pseudo-sections all tagged with section_id='item_8'.
    #     Each one covers from its heading to the start of the next financial
    #     statement heading (or the next Item heading, or end of doc).
    #     """
    #     fs_matches = list(FINANCIAL_STATEMENT_PATTERN.finditer(text))
    #     if not fs_matches:
    #         return []

    #     # Build a sorted list of all "stop points" — any next heading would
    #     # mark the end of the current financial-statement block. Stop points
    #     # include other financial-statement headings AND any item-section heading.
    #     stop_points = sorted(
    #         [m.start() for m in fs_matches] + [s.char_start for s in item_sections]
    #     )

    #     pseudo_sections: list[ParsedSection] = []
    #     for match in fs_matches:
    #         start = match.start()
    #         # Find the next stop point after this match's start
    #         next_stop = next((p for p in stop_points if p > start), len(text))

    #         fs_text = text[start:next_stop].strip()
    #         if len(fs_text) < 200:
    #             continue

    #         title_raw = match.group(0).strip()
    #         # Normalize the title to one line
    #         title = " ".join(title_raw.split())

    #         pseudo_sections.append(
    #             ParsedSection(
    #                 section_id="item_8",
    #                 title=f"Item 8. {title}",
    #                 text=fs_text,
    #                 char_start=start,
    #                 char_end=next_stop,
    #             )
    #         )

    #     return pseudo_sections

    def _merge_financial_into_item_8(
        self,
        item_sections: list[ParsedSection],
        financial_sections: list[ParsedSection],
    ) -> list[ParsedSection]:
        """Combine all financial-statement pseudo-sections into a single item_8.

        Strategy: concatenate the existing item_8 (if any) with all financial-
        statement sections, separated by their titles. This produces one big
        item_8 section that contains the actual financial data, which the
        chunker will then split into multiple chunks under the 'financials' label.
        """
        # Pull out the existing item_8 (if any) from the item-sections list
        existing_item_8 = next(
            (s for s in item_sections if s.section_id == "item_8"), None
        )
        other_sections = [s for s in item_sections if s.section_id != "item_8"]

        # Build the merged financial-statements text
        parts: list[str] = []
        if existing_item_8 is not None:
            parts.append(existing_item_8.text)
        for fs in financial_sections:
            parts.append(f"\n\n{fs.title}\n\n{fs.text}")

        merged_text = "\n\n".join(parts)
        merged_start = (
            existing_item_8.char_start
            if existing_item_8 is not None
            else financial_sections[0].char_start
        )
        merged_end = max(
            (s.char_end for s in financial_sections),
            default=existing_item_8.char_end if existing_item_8 else 0,
        )

        merged_item_8 = ParsedSection(
            section_id="item_8",
            title="Item 8. Financial Statements and Supplementary Data",
            text=merged_text,
            char_start=merged_start,
            char_end=merged_end,
        )

        # Return the consolidated section list, sorted by position
        return sorted(other_sections + [merged_item_8], key=lambda s: s.char_start)

    def _extract_sections(self, text: str) -> list[ParsedSection]:
        """Find real Item N section boundaries, filtering TOC/cross-reference noise.

        The naive approach (every Item-N match is a section) produces 60+ candidates
        per filing because Item-N appears in:
          - The TOC entry ("Item 1A. Risk Factors ........ 12")
          - Cross-references ("see Item 7A for more detail")
          - Exhibits index footers
          - And the actual section start (what we want)

        We use three structural-signal filters to reject non-section matches before
        dedup runs. This generalizes across filers (NVDA, AAPL, older industrials)
        rather than papering over the symptom with smarter dedup.
        """
        matches = list(SECTION_PATTERN.finditer(text))

        if not matches:
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

        # Filter matches using structural signals — keep only real section headers
        real_matches = [m for m in matches if self._is_real_section_header(m, text, matches)]

        log.info(
            "parser.section_filter",
            total_matches=len(matches),
            kept_as_real=len(real_matches),
            rejected_as_noise=len(matches) - len(real_matches),
        )

        if not real_matches:
            log.warning("parser.all_matches_rejected_falling_back_to_naive")
            real_matches = matches  # safety fallback

        sections: list[ParsedSection] = []
        for i, match in enumerate(real_matches):
            item_num = match.group(2).lower()
            title_remainder = match.group(3).strip()
            title = f"Item {item_num.upper()}. {title_remainder}".strip(". ")

            start = match.start()
            # End at the next real section's start, or end of doc
            if i + 1 < len(real_matches):
                end = real_matches[i + 1].start()
            else:
                end = len(text)

            section_text = text[start:end].strip()

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

        # Dedup by section_id, keeping largest
        by_id: dict[str, ParsedSection] = {}
        for s in sections:
            existing = by_id.get(s.section_id)
            if existing is None or len(s.text) > len(existing.text):
                by_id[s.section_id] = s

        return sorted(by_id.values(), key=lambda s: s.char_start)

    def _is_real_section_header(
        self,
        match: re.Match,
        text: str,
        all_matches: list[re.Match],
    ) -> bool:
        """Apply three structural filters to classify a regex match as real-vs-noise.

        Returns True only if the match looks like a genuine section header.

        Filter 1: TOC fingerprint — followed by dots and page numbers
        Filter 2: Cross-reference — preceded by 'see', 'refer to', 'under'
        Filter 3: Substantial content — at least 500 chars before next match
        """
        pos = match.start()

        # Look at surrounding context windows
        before = text[max(0, pos - 80):pos].lower()
        after_window = text[pos:pos + 200]

        # FILTER 1: TOC fingerprint
        # Real TOC entries look like "Item 1A. Risk Factors ........... 12"
        # The dots and page number are the giveaway. Regex catches:
        #   - 3+ dots, optional whitespace, then digits within 200 chars
        #   - or a tab/multi-space gap then digits (some filers use whitespace)
        if re.search(r"\.{3,}\s*\d+\b", after_window):
            return False
        if re.search(r"\s{4,}\d+\s*$", after_window[:120].split("\n")[0]):
            return False

        # FILTER 2: Cross-reference fingerprint (TIGHTER)
        # Only match phrases that are unambiguously cross-references to OTHER Items.
        # A real cross-reference looks like "see Item 7A" or "refer to Item 1A" —
        # the word "Item" must appear NEAR the trigger word, not just somewhere.
        # We check a 30-char window before the match for both the trigger AND "item"
        before_window = text[max(0, pos - 30):pos].lower()
        if re.search(
            r"\b(see|refer\s+to|set\s+forth\s+in|incorporated\s+(?:by\s+reference\s+)?in)\s+$",
            before_window,
        ):
            return False

        

        # FILTER 3: Substantial content
        # Real sections have at least 500 chars of content before the next match.
        # Bare pointers and ToC artifacts don't.
        next_match_pos = None
        for m in all_matches:
            if m.start() > pos:
                next_match_pos = m.start()
                break

        content_length = (next_match_pos or len(text)) - pos
        if content_length < 500:
            return False

        return True