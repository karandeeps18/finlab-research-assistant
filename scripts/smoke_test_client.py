import asyncio

from finlab_research_assistant.core.logging import configure_logging, get_logger
from finlab_research_assistant.ingestion.edgar_client import EdgarClient

configure_logging("INFO")
log = get_logger(__name__)


async def main() -> None:
    url = "https://www.sec.gov/files/company_tickers.json"

    async with EdgarClient() as client:
        data = await client.get_json(url)
    for i, (_key, entry) in enumerate(data.items()):
        if i >= 3:
            break
        log.info(
            "company_loaded",
            ticker=entry["ticker"],
            cik=entry["cik_str"],
            name=entry["title"],
        )

    log.info("smoke_test.complete", total_companies=len(data))


if __name__ == "__main__":
    asyncio.run(main())