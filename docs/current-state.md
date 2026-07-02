# Current State

A candid snapshot of what is built, what is partial, and what is a placeholder — so the
[Roadmap](roadmap.md) has an honest starting point.

## Working end to end

- **Ingestion** (`ingestion/`): ticker resolution, filing-history fetch, rate-limited
  retrying downloads, immutable raw storage with provenance, idempotent re-runs, and
  company/filing catalog sync.
- **Parsing** (`parsing/parser.py`): Item-N section extraction with structural noise
  filters; verified across NVDA and AAPL.
- **Chunking** (`chunking/chunker.py`): section-aware, priority-weighted, overlapping
  chunks with title-prefix context and char-offset provenance.
- **Catalog** (`db/`): async SQLAlchemy models, upserts, and delete-then-insert chunk
  persistence.
- **Embedding contracts + batching** (`embedding/contracts.py`, `embedding/batcher.py`):
  typed limits/items, provider protocol, fail-fast validation, greedy next-fit batching,
  and a deterministic `FakeProvider`.

## Partial

| Item | State |
|------|-------|
| Real embedding provider | `voyage-finance-2` is configured; no `VoyageProvider` implemented. |
| `Embedder` orchestrator | `embedding/embedder.py` is a 2-line stub. |
| Parser Pass 2 (financial statements → `item_8`) | Implemented but **commented out**; helper `_extract_financial_statements` disabled. |
| Schema migrations | `alembic` declared; no migrations — `init_db()`/`create_all` only. |

## Not started (empty packages)

- `retrieval/` — hybrid dense + BM25 search, section-label filtering, priority ranking.
- `generation/` — Claude-based answer/memo generation with citations.
- `evaluation/` — retrieval/answer quality metrics.
- `api/` — FastAPI surface (dependency present, no routes).
- **Vector store** — `chromadb` installed and `chroma_dir` configured, but nothing reads
  or writes it.

## Known issues / cleanups

- **Duplicate `Ingestor`.** `ingestion/ingestor.py` and `db/ingestor.py` are identical;
  only the former is used.
- **Token counts are character estimates** (`len // 4`), not real tokens.
- **No orchestrated full pipeline.** Parsing and chunk persistence are wired only in the
  smoke-test scripts, not behind a single entrypoint or CLI.
- **Recent-only filing history.** Paginated older submissions (`filings.files[*]`) are not
  followed.
- **Temporal columns unused.** `filing_date` / `report_date` / `ingested_at` are stored but
  no as-of / amendment / supersession logic consumes them.

## Test coverage

Verification today is via runnable **smoke tests** in `scripts/` (ingestion, parsing,
chunking, DB, batcher, fake-embed) rather than a `pytest` suite, though `pytest` /
`pytest-asyncio` are configured for adding one.
