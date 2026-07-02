# Design Decisions

The trade-offs below are drawn directly from the code and its comments. They explain *why*
the system is shaped the way it is, and where the deliberate limits are.

## Rule-based section taxonomy over a learned classifier

The chunker hard-codes `SECTION_TAXONOMY` (which items to keep, their sizes and
priorities). The comment in `chunker.py` is explicit about the trade-off:

> Rule-based section weights are fragile (10-K structure evolves across companies and
> years). A learned classifier on past filings would be more robust at scale. We stay
> rule-based for clarity and auditability.

**Why:** at this stage, a transparent, auditable rule set is preferable to an opaque model;
every decision (for example, why Item 4 is excluded) is answerable by reading a dictionary.
**Cost:** brittleness across unusual filers; new or renamed items fall through to
`_default`.

## Structural filters over more elaborate de-duplication in the parser

A naive rule that treats every `Item N` match as a section yields 60+ candidates per
filing. Rather than address this with more elaborate de-duplication, the parser rejects
non-headers using **structural signals** (dot-leaders and page numbers, cross-reference
proximity, minimum content length).

**Why:** structural signals generalize across issuers (NVDA, AAPL, older industrials);
issuer-specific dedup does not. **Cost:** the filters are heuristics with a safety fallback
(if all matches are rejected, treat them all as real).

## Bronze/Silver/Gold with an immutable raw layer

Downloaded filings are written once and never modified; parsed/chunked representations are
derived and regenerable; the DB catalog records what exists.

**Why:** reproducibility. The same raw bytes always yield the same downstream artifacts, so
reprocessing is safe and results are auditable. **Cost:** disk duplication of source
documents (acceptable at this scale).

## Idempotency by construction

- Raw layer: a `metadata.json` marker (written **last**) signals completion; partial
  downloads are re-fetched.
- Catalog: `upsert_*` select-then-insert; `persist_chunks` deletes prior chunks before
  inserting.

**Why:** re-runs must converge to the same state without manual cleanup. **Cost:** the
completion-marker scheme is coarse (file-level, not checksum-verified).

## `Protocol` over ABC for the embedding provider

`EmbeddingProvider` is a `typing.Protocol`. Any object exposing a matching asynchronous
`embed` method conforms, without inheritance.

**Why:** structural typing keeps providers decoupled and makes the deterministic
`FakeProvider` straightforward to implement for tests. **Cost:** conformance is checked
structurally, not enforced by a base class at definition time.

## Validate-then-batch (fail-fast) in embedding

`validate_items` scans for any oversized item and raises **before** `batch_items` yields
anything.

**Why:** this guarantees that if validation passes, every produced batch is valid, with no
partial progress in which a later item exceeds the per-item limit mid-stream. **Cost:** one
additional linear pass over the items.

## Separate Pydantic DTOs and SQLAlchemy ORM

EDGAR JSON is parsed into Pydantic models at the HTTP boundary (`ingestion/models.py`);
persistence uses distinct ORM classes (`db/models.py`); mapping happens in the repository.

**Why:** a schema change at the EDGAR boundary surfaces at a single, well-defined point,
and the persistence layer can evolve independently. **Cost:** two parallel model definitions and an
explicit mapping step.

## Character-based token approximation

`token_count = len(text) // 4`, and batch limits are enforced against this proxy.

**Why:** avoids a tokenizer dependency in the hot path and keeps chunking deterministic and
fast. **Cost:** batch token budgeting is approximate; a real tokenizer is needed before
trusting the `max_tokens_per_batch` ceiling against a strict provider limit. Tracked in the
[Roadmap](roadmap.md).

## SQLite + async SQLAlchemy, `create_all` for now

The catalog is local SQLite via `aiosqlite`, with tables created by `init_db()`.

**Why:** zero-ops local development; async keeps it consistent with the httpx/asyncio I/O
model. **Cost:** `create_all` is not migration-safe — `alembic` is present but unused, so
schema changes currently require recreating the DB.
