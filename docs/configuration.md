# Configuration

**File:** `core/config.py` · **Mechanism:** `pydantic-settings`

All configuration is centralized in a single typed `Settings` object loaded from
environment variables (and a local `.env`). Validation happens at import time — if a
required variable is missing, the process **fails fast at startup** rather than at first
use.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )

settings = Settings()  # module-level singleton
```

## Settings surface

| Setting | Env var | Default | Required |
|---------|---------|---------|:--------:|
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | — | ✅ |
| `edgar_user_agent` | `EDGAR_USER_AGENT` | — | ✅ |
| `edgar_base_url` | `EDGAR_BASE_URL` | `https://www.sec.gov` | |
| `edgar_data_url` | `EDGAR_DATA_URL` | `https://data.sec.gov` | |
| `edgar_max_requests_per_second` | `EDGAR_MAX_REQUESTS_PER_SECOND` | `9` | |
| `voyage_api_key` | `VOYAGE_API_KEY` | `None` | |
| `embedding_model` | `EMBEDDING_MODEL` | `voyage-finance-2` | |
| `database_url` | `DATABASE_URL` | `sqlite+aiosqlite:///./data/finlab.db` | |
| `project_root` | — | repo root (derived from `__file__`) | |
| `data_dir` | — | `{project_root}/data` | |
| `raw_dir` | — | `{data_dir}/raw` | |
| `processed_dir` | — | `{data_dir}/processed` | |
| `chroma_dir` | — | `{data_dir}/chroma` | |

!!! warning "Required even where unused"
    `anthropic_api_key` is **required** at import, even though no code calls Anthropic yet
    — importing `settings` without it set will raise. `edgar_user_agent` is genuinely
    required by SEC (format: `Your Name your.email@example.com`). `voyage_api_key` is
    optional because the real embedding provider is not wired.

## Example `.env`

```bash title=".env"
ANTHROPIC_API_KEY=sk-ant-...
EDGAR_USER_AGENT=Jane Doe jane@example.com
VOYAGE_API_KEY=pa-...            # optional until the Voyage provider lands
# DATABASE_URL=sqlite+aiosqlite:///./data/finlab.db
```

## Logging — `core/logging.py`

`configure_logging(level)` sets up `structlog` for structured, machine-readable events;
`get_logger(__name__)` returns a bound logger. Every module logs typed events
(`filing.written`, `parser.section_filter`, `chunks.persisted`, …) rather than free text,
which makes runs greppable and inspectable.

## Dependencies

Declared in `pyproject.toml` (`requires-python >= 3.11`). Grouped by how they are used
today:

=== "Used now"

    | Package | Role |
    |---------|------|
    | `httpx` | async EDGAR HTTP client |
    | `tenacity` | retry with exponential backoff |
    | `unstructured` | HTML → text partitioning in the parser |
    | `pydantic`, `pydantic-settings` | typed DTOs + settings |
    | `sqlalchemy`, `aiosqlite`, `greenlet` | async catalog |
    | `structlog` | structured logging |
    | `python-dotenv` | `.env` loading |

=== "Installed, not yet used"

    | Package | Intended for |
    |---------|--------------|
    | `voyageai` | real embedding provider |
    | `chromadb` | vector store |
    | `rank-bm25` | sparse retrieval in hybrid search |
    | `anthropic` | Claude generation |
    | `fastapi`, `uvicorn` | HTTP API surface |
    | `alembic` | schema migrations |
    | `pypdf` | non-HTML document parsing |

=== "Dev"

    | Package | Role |
    |---------|------|
    | `pytest`, `pytest-asyncio` | tests |
    | `ruff` | lint/format |
    | `datasette` | ad-hoc SQL inspection of `finlab.db` |

Dependency and lockfile management is via **uv** (`uv.lock`, `uv_build` backend).
