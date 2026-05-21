"""Smoke test: parse the NVDA 10-K we ingested."""

from pathlib import Path

from finlab_research_assistant.core.config import settings
from finlab_research_assistant.core.logging import configure_logging, get_logger
from finlab_research_assistant.parsing.parser import FilingParser

configure_logging("INFO")
log = get_logger(__name__)


def main() -> None:
    # Find the NVDA filing on disk
    nvda_dir = next((settings.raw_dir / "NVDA").iterdir())
    html_path = nvda_dir / "filing.html"

    parser = FilingParser()
    parsed = parser.parse(
        raw_html_path=html_path,
        ticker="NVDA",
        accession_number=nvda_dir.name,
    )

    log.info("parse.complete", total_sections=len(parsed.sections))
    for s in parsed.sections[:10]:
        log.info(
            "section",
            id=s.section_id,
            title=s.title[:80],
            chars=len(s.text),
        )


if __name__ == "__main__":
    main()