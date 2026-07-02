# Architecture

## Layered design

The system follows a **Bronze/Silver/Gold** data-engineering pattern: an immutable raw
layer on disk, derived parsed/chunked representations, and a metadata catalog that is the
source of truth for "what has been ingested." Each stage is a small, single-responsibility
module with typed inputs and outputs.

```mermaid
flowchart TB
    subgraph external[External]
        EDGAR[(SEC EDGAR)]
    end

    subgraph ingest[Ingestion — implemented]
        RES[CompanyResolver<br/>ticker → CIK]
        IDX[FilingsIndex<br/>submissions history]
        CLI[EdgarClient<br/>async + rate limit + retry]
        STO[RawStorage<br/>immutable bronze layer]
    end

    subgraph process[Processing — implemented]
        PAR[FilingParser<br/>HTML → sections]
        CHU[SectionAwareChunker<br/>sections → chunks]
    end

    subgraph persist[Catalog — implemented]
        DB[(SQLite<br/>companies / filings / chunks)]
    end

    subgraph embed[Embedding — partial]
        BAT[batcher<br/>greedy next-fit]
        PRV[EmbeddingProvider<br/>Fake ✓ / Voyage ✗]
        VEC[(Vector store<br/>Chroma — not wired)]
    end

    subgraph future[Not built yet]
        RET[retrieval]
        GEN[generation]
        EVAL[evaluation]
        API[api]
    end

    EDGAR --> CLI
    CLI --> RES & IDX & STO
    RES --> IDX --> STO
    STO -->|filing.html| PAR
    PAR -->|ParsedFiling| CHU
    CHU -->|Chunk[]| DB
    STO -.metadata.-> DB
    DB -->|chunks| BAT --> PRV --> VEC
    VEC -.-> RET --> GEN
    DB -.-> EVAL
    GEN -.-> API
```

Solid arrows denote data flows implemented in code; dashed arrows denote planned
connections that are not yet implemented.

## Module map

```
src/finlab_research_assistant/
├── core/
│   ├── config.py          # pydantic-settings; env-driven, fail-fast at import
│   └── logging.py          # structlog configuration
├── ingestion/
│   ├── edgar_client.py     # async HTTP: rate limiting + retries
│   ├── company_resolver.py # ticker → CIK via cached company_tickers.json
│   ├── filings_index.py    # submissions endpoint → list[Filing]
│   ├── storage.py          # immutable raw layer + idempotency marker
│   ├── ingestor.py         # end-to-end orchestrator
│   └── models.py           # Pydantic DTOs (Company, Filing)
├── parsing/
│   ├── parser.py           # 10-K HTML → ParsedSection[]
│   └── models.py           # ParsedSection, ParsedFiling
├── chunking/
│   └── chunker.py          # SECTION_TAXONOMY + SectionAwareChunker + Chunk
├── embedding/
│   ├── contracts.py        # BatchLimits, BatchItem, EmbeddingProvider protocol
│   ├── batcher.py          # validate_items + batch_items (greedy next-fit)
│   ├── providers.py        # FakeProvider (deterministic)
│   └── embedder.py         # STUB (2-line docstring)
├── db/
│   ├── models.py           # SQLAlchemy ORM: Company, Filing, Chunk
│   ├── repository.py       # upsert_company / upsert_filing / persist_chunks
│   ├── session.py          # async engine + get_session() + init_db()
│   └── ingestor.py         # DUPLICATE of ingestion/ingestor.py (see note)
├── retrieval/  · generation/  · evaluation/  · api/   # empty packages
```

!!! note "Two identical `Ingestor` classes"
    `ingestion/ingestor.py` and `db/ingestor.py` currently contain the **same**
    `Ingestor` class verbatim. Only `ingestion/ingestor.py` is imported by the smoke
    tests. The duplicate should be removed — tracked in the [Roadmap](roadmap.md).

## Design principles

- **Typed boundaries.** Raw EDGAR JSON is parsed into Pydantic DTOs
  (`ingestion/models.py`) at the HTTP boundary; downstream code only sees typed objects.
  A separate SQLAlchemy ORM (`db/models.py`) owns persistence. DTO → ORM mapping happens
  in `db/repository.py`.
- **Idempotency at every layer.** Re-running ingestion skips already-downloaded filings
  (a `metadata.json` marker) but always re-syncs the catalog; `persist_chunks` deletes a
  filing's prior chunks before inserting, so reprocessing is clean and repeatable.
- **Immutability of raw data.** Once written, `filing.html` is never modified;
  reprocessing regenerates the derived layers.
- **Structured logging.** Every stage emits structured `structlog` events
  (`parser.section_filter`, `chunker.complete`, `db_sync.complete`, …) instead of prose
  logs, so runs are machine-inspectable.

See [Design Decisions](design-decisions.md) for the trade-offs behind these choices.
