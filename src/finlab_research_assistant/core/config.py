from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    Values are loaded from environment variables.
    Type validation happens at startup — failfast pattern
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- API credentials ---
    anthropic_api_key: str = Field(..., description="Anthropic API key for Claude")

    # --- EDGAR ---
    # SEC requires every request to identify user (Format: "Your Name your.email@example.com)"
    edgar_user_agent: str = Field(
        ...,
        description="Required by SEC. Format: 'Your Name your.email@example.com'",
    )
    edgar_base_url: str = "https://www.sec.gov"
    edgar_data_url: str = "https://data.sec.gov"
    edgar_max_requests_per_second: int = 9

    # --- Embedding ---
    voyage_api_key: str | None = None  # add 
    embedding_model: str = "voyage-3"

    # --- Storage paths ---
    project_root: Path = Path(__file__).resolve().parents[3] 
    data_dir: Path = project_root / "data"
    raw_dir: Path = data_dir / "raw"
    processed_dir: Path = data_dir / "processed"
    chroma_dir: Path = data_dir / "chroma"
    
    # -- Database -- 
    database_url: str = "sqlite+aiosqlite:///./data/finlab.db"


# Module-level singleton
settings = Settings()  # type: ignore[call-arg]