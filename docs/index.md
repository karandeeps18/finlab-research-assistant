# FinLab Research Assistant

FinLab Research Assistant is a Python pipeline that turns **SEC EDGAR 10-K filings**
into a structured, queryable corpus for investment research. It downloads filings,
parses them into named sections, splits those sections into retrieval-ready chunks with
provenance, and (in progress) embeds those chunks into vectors.

This documentation describes the system **as it exists in the code today**, including
components that are implemented, partial, or still stubs. It is a technical reference,
not a marketing document. For the product/vision framing, see the separate
[pitch document](https://github.com/karandeeps18/finlab-research-assistant/blob/master/docs/PITCH.md)
on the `feat/embedding` branch.

## What it does today

1. **Ingest** — resolve a ticker to a CIK, fetch its filing history from EDGAR, download
   the latest 10-K, and store it immutably on disk with provenance metadata.
2. **Parse** — extract Item-N narrative sections (Item 1, 1A, 7, …) from the filing HTML,
   filtering out table-of-contents and cross-reference noise.
3. **Chunk** — split each whitelisted section into overlapping, size-tuned chunks tagged
   with a section label, a retrieval priority, and character-offset provenance.
4. **Catalog** — persist companies, filings, and chunks into a SQLite metadata database
   via an async SQLAlchemy layer.

Embedding, retrieval, generation, and evaluation are **partially built or scaffolded** —
see [Current State](current-state.md).

## Component status at a glance

| Area | Module | Status |
|------|--------|--------|
| Ingestion | `ingestion/` | :material-check: Implemented |
| Parsing | `parsing/parser.py` | :material-check: Implemented (Pass 2 disabled) |
| Chunking | `chunking/chunker.py` | :material-check: Implemented |
| Metadata catalog | `db/` | :material-check: Implemented |
| Embedding contracts + batching | `embedding/contracts.py`, `embedding/batcher.py` | :material-check: Implemented |
| Real embedding provider | `embedding/providers.py`, `embedding/embedder.py` | :material-progress-helper: Fake provider only; Voyage + orchestrator stub |
| Vector store | (Chroma configured) | :material-close: Not wired |
| Retrieval | `retrieval/` | :material-close: Empty package |
| Generation | `generation/` | :material-close: Empty package |
| Evaluation | `evaluation/` | :material-close: Empty package |
| HTTP API | `api/` | :material-close: Empty package |

## Where to start

- [Architecture](architecture.md) — the module map and end-to-end data flow.
- [Pipeline](pipeline/ingestion.md) — a page per stage (ingestion → parsing → chunking → embedding).
- [Data Model](data-model.md) — the SQLite catalog schema.
- [Running It](running.md) — how to execute each stage via the `scripts/` smoke tests.
- [Roadmap](roadmap.md) — prioritized next steps.

## Tech stack

Python ≥ 3.11, `httpx` + `tenacity` (EDGAR I/O), `unstructured` (HTML parsing),
`pydantic` / `pydantic-settings` (typed boundaries + config), SQLAlchemy 2.0 async +
`aiosqlite` (catalog), `voyageai` (embeddings), `structlog` (logging). Installed but not
yet used: `chromadb`, `rank-bm25`, `anthropic`, `fastapi`/`uvicorn`, `alembic`. See
[Configuration](configuration.md#dependencies) for the full inventory.
