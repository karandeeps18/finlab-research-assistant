"""Parsed-filing data models."""

from __future__ import annotations

from pydantic import BaseModel


class ParsedSection(BaseModel):
    """A section of a 10-K (e.g., 'Item 1A. Risk Factors')."""

    section_id: str          # normalized, e.g. "item_1a"
    title: str               # human title, e.g. "Item 1A. Risk Factors"
    text: str                # raw text content
    char_start: int          # offset in the full document
    char_end: int


class ParsedFiling(BaseModel):
    """A 10-K parsed into structured sections."""

    accession_number: str
    ticker: str
    sections: list[ParsedSection]
    full_text: str           # concatenated, for fallback retrieval
    char_count: int