import asyncio
from pathlib import Path
from finlab_research_assistant.core.config import settings
from finlab_research_assistant.parsing.parser import FilingParser

async def diag():
    nvda_dir = next((settings.raw_dir / "NVDA").iterdir())
    parser = FilingParser()
    parsed = parser.parse(
        raw_html_path=nvda_dir / "filing.html",
        ticker="NVDA",
        accession_number=nvda_dir.name,
    )
    
    print("=" * 70)
    print(f"Total sections: {len(parsed.sections)}")
    print("=" * 70)
    for s in parsed.sections:
        print(f"{s.section_id:15s}  pos={s.char_start:>7d}  chars={len(s.text):>6d}  title={s.title[:60]}")

asyncio.run(diag()) if False else None
# Or just call diag() inside an event loop, or convert to sync — parser.parse is sync anyway

# Sync version:
def diag_sync():
    nvda_dir = next((settings.raw_dir / "NVDA").iterdir())
    parser = FilingParser()
    parsed = parser.parse(
        raw_html_path=nvda_dir / "filing.html",
        ticker="NVDA",
        accession_number=nvda_dir.name,
    )
    print("=" * 70)
    print(f"Total sections: {len(parsed.sections)}")
    print("=" * 70)
    for s in parsed.sections:
        print(f"{s.section_id:15s}  pos={s.char_start:>7d}  chars={len(s.text):>6d}  title={s.title[:60]}")

diag_sync()