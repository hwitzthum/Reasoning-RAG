"""Configuration management using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    anthropic_api_key: str

    # Paths
    database_url: str = "sqlite+aiosqlite:///./data/reasoning_rag.db"
    documents_path: Path = Path("./documents")

    # Reasoning Parameters
    max_reasoning_iterations: int = 8
    query_timeout_seconds: int = 60
    ingestion_timeout_seconds: int = 300

    # Cache Runtime Controls (Phase 3)
    dry_run_cache_only: bool = False
    query_cache_ttl_seconds: int = 86_400

    # Runtime protections (Tier 2)
    query_rate_limit_requests_per_minute: int = 100
    max_concurrent_queries: int = 5
    projected_query_cost_usd: float = 5.28
    max_projected_query_cost_usd: float = 10.0

    # LLM Models
    reasoning_model: str = "claude-sonnet-4-6"
    annotation_model: str = "claude-haiku-4-5-20251001"

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
