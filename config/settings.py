"""Centralized Application Configuration & Environment Settings.

Manages environment variables, Groq LLM integration parameters, database paths,
logging configurations, and dynamic fallback toggles.
"""

from functools import lru_cache
import logging
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine the project root directory (one level up from config/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings backed by environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project Paths
    ROOT_DIR: Path = PROJECT_ROOT
    DATA_DIR: Path = PROJECT_ROOT / "data"

    # LLM Settings
    LLM_PROVIDER: str = Field(
        default="groq",
        description="LLM provider name (default: groq)",
    )
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for Groq Cloud inference",
    )
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="High-reasoning Groq model for extraction & clustering",
    )
    GROQ_FAST_MODEL: str = Field(
        default="llama-3.1-8b-instant",
        description="High-throughput Groq model for fast triage & relevance filtering",
    )

    # Operational Modes
    OFFLINE_MODE: bool = Field(
        default=False,
        description="Explicit flag to force deterministic offline fallback mode",
    )
    USE_DENSE_EMBEDDINGS: bool = Field(
        default=False,
        description="Whether to use heavy sentence-transformers instead of fast TF-IDF",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Database Configuration
    DB_PATH: str = Field(
        default="data/app_database.sqlite",
        description="Relative or absolute path to SQLite database file",
    )

    @property
    def is_offline(self) -> bool:
        """Determines if the application should execute in deterministic offline fallback mode.

        Returns True if:
        1. OFFLINE_MODE is explicitly set to True, OR
        2. GROQ_API_KEY is not provided, empty, or whitespace-only.
        """
        if self.OFFLINE_MODE:
            return True
        if not self.GROQ_API_KEY or not self.GROQ_API_KEY.strip():
            return True
        return False

    @property
    def absolute_db_path(self) -> Path:
        """Returns the fully qualified filesystem Path to the SQLite database."""
        p = Path(self.DB_PATH)
        if p.is_absolute():
            return p
        return (self.ROOT_DIR / p).resolve()

    @property
    def database_url(self) -> str:
        """Constructs an SQLAlchemy-compatible SQLite connection URL."""
        return f"sqlite:///{self.absolute_db_path.as_posix()}"

    def ensure_directories(self) -> None:
        """Ensures that required persistent data and export directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        (self.DATA_DIR / "raw").mkdir(parents=True, exist_ok=True)
        (self.DATA_DIR / "golden").mkdir(parents=True, exist_ok=True)
        (self.DATA_DIR / "exports").mkdir(parents=True, exist_ok=True)
        self.absolute_db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached singleton instance of application settings."""
    settings = Settings()
    settings.ensure_directories()
    return settings


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """Configures structured application logging."""
    settings = get_settings()
    log_level_name = (level or settings.LOG_LEVEL).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("ai_discovery_engine")
    logger.setLevel(log_level)
    return logger

