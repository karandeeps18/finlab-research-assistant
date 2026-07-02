# Running It

There is **no CLI or HTTP API yet**. The pipeline is exercised through the scripts in
`scripts/`, which double as smoke tests. Each stage can be run independently; together they
demonstrate the full ingest → parse → chunk → persist flow.

## Setup

```bash
# 1. Install dependencies (uv manages the venv from uv.lock)
uv sync

# 2. Provide required configuration (see Configuration page)
cp .env.example .env   # if present; otherwise create .env
#   ANTHROPIC_API_KEY=...        (required at import)
#   EDGAR_USER_AGENT=Name email  (required by SEC)
```

## Scripts

| Script | What it does |
|--------|--------------|
| `scripts/smoke_test_client.py` | Exercises `EdgarClient` (headers, rate limit, retry). |
| `scripts/smoke_test_filings.py` | Resolves a ticker and fetches its filing index. |
| `scripts/smoke_test_ingest.py` | Full ingestion of a ticker's latest 10-K to disk. |
| `scripts/smoke_test_db.py` | Ingest + persist company/filing rows, then query them back. |
| `scripts/smoke_test_parse.py` | Parse a downloaded 10-K into sections. |
| `scripts/diag_sections.py` | Diagnostic dump of detected vs rejected section headers. |
| `scripts/smoke_test_chunk.py` | Ingest → parse → chunk → persist chunks (NVDA). |
| `scripts/smoke_test_aapl_chunk.py` | Same, for AAPL — checks cross-issuer generalization. |
| `scripts/batcher_test.py` | Unit-style checks for the embedding batcher. |
| `scripts/smoke_test_fake_embed.py` | Validates the `FakeProvider` contract. |
| `scripts/voyage_api_test.py` | Reference for the intended Voyage call shape. |

## The end-to-end path

`scripts/smoke_test_chunk.py` is the most complete single run and demonstrates how the
stages are composed:

```python
# 1. schema
await init_db()

# 2. ingest (idempotent) — company + filing rows + raw filing.html
ingestor = Ingestor()
async with EdgarClient() as client:
    await ingestor.ingest_latest_filing("NVDA", "10-K", client)

# 3. parse the downloaded HTML into sections
parsed = FilingParser().parse(
    raw_html_path=nvda_dir / "filing.html",
    ticker="NVDA", accession_number=nvda_dir.name,
)

# 4. chunk with the section taxonomy
chunks = SectionAwareChunker().chunk_filing(parsed)

# 5. persist chunks (delete-then-insert for the filing)
async with get_session() as session:
    filing = (await session.execute(
        select(Filing).where(Filing.accession_number == nvda_dir.name)
    )).scalar_one()
    await persist_chunks(session, filing, chunks)
```

```bash
uv run python scripts/smoke_test_chunk.py
```

!!! note "Parsing/chunking are not in the orchestrator"
    `Ingestor` only syncs company + filing rows. Parsing and chunk persistence are invoked
    explicitly by the scripts above. A single orchestrated `ingest → … → persist_chunks`
    entrypoint (and a CLI) is future work — see the [Roadmap](roadmap.md).

## Inspecting results

The catalog is a plain SQLite file (`data/finlab.db`). Inspect it with the bundled
`datasette` dev dependency:

```bash
uv run datasette data/finlab.db
```

Useful checks: chunk counts grouped by `section_label` and `priority` (as
`smoke_test_chunk.py` prints), and a sample `risk_factors` chunk to confirm the
title-prefix and content.

## Building these docs locally

```bash
uvx --with mkdocs-material mkdocs serve   # live preview at http://127.0.0.1:8000
uvx --with mkdocs-material mkdocs build --strict
```
