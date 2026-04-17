"""Configuration management using pydantic-settings."""

import json
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env.local", case_sensitive=False)

    # Postgres configuration
    postgres_host: str = Field(..., description="PostgreSQL host")
    postgres_port: int = Field(..., description="PostgreSQL port")
    postgres_db: str = Field(..., description="PostgreSQL database name")
    postgres_user: str = Field(..., description="PostgreSQL user")
    postgres_password: str = Field(..., description="PostgreSQL password")

    # Chainlit configuration
    chainlit_host: str = Field(..., description="Chainlit host")
    chainlit_port: int = Field(..., description="Chainlit port")

    # Application environment
    app_env: str = Field(..., description="Application environment (local, prod)")
    app_version: str = Field(default="1.0.0", description="Application version number")

    # OpenRouter configuration
    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_model_llm: str = Field(..., description="OpenRouter LLM model name")
    openrouter_model_vlm: str = Field(..., description="OpenRouter VLM model name")
    openrouter_fallback_model_llm: str = Field(..., description="Fallback LLM model when primary returns 402")
    openrouter_fallback_model_vlm: str = Field(..., description="Fallback VLM model when primary returns 402")
    openrouter_base_url: str = Field(..., description="OpenRouter base URL")
    openrouter_max_retries: int = Field(..., description="OpenRouter max retry count")
    openrouter_retry_delay: float = Field(..., description="OpenRouter retry delay in seconds")
    openrouter_vlm_max_tokens: int = Field(..., description="Max tokens for VLM response generation")
    openrouter_llm_max_tokens: int = Field(..., description="Max tokens for LLM response generation")
    openrouter_llm_temperature: float = Field(..., description="LLM temperature (lower for reasoning models)")
    openrouter_timeout: int = Field(..., description="LLM call timeout in seconds")
    intake_agent_mode: str = Field(
        default="legacy",
        description="Intake agent mode selector: 'legacy' or 'gpt'",
    )

    # Qdrant configuration
    qdrant_host: str = Field(..., description="Qdrant host")
    qdrant_port: int = Field(..., description="Qdrant port")

    # SMTP configuration (for email MCP server)
    smtp_host: str = Field(default="mailhog", description="SMTP host")
    smtp_port: int = Field(default=1025, description="SMTP port")
    smtp_user: str = Field(default="", description="SMTP username (optional)")
    smtp_password: str = Field(default="", description="SMTP password (optional)")

    # MCP Server URLs
    rag_mcp_url: str = Field(..., description="RAG MCP server URL")
    db_mcp_url: str = Field(..., description="Database MCP server URL")
    currency_mcp_url: str = Field(..., description="Currency conversion MCP server URL")
    email_mcp_url: str = Field(..., description="Email MCP server URL")

    # Image Quality Settings
    image_quality_threshold: float = Field(..., description="Laplacian variance threshold for blur detection")
    image_min_width: int = Field(..., description="Minimum image width in pixels")
    image_min_height: int = Field(..., description="Minimum image height in pixels")

    # VLM Confidence Threshold
    vlm_confidence_threshold: float = Field(..., description="Minimum VLM confidence before asking human")

    # Session configuration
    session_secret_key: str = Field(..., description="Secret key for signing session cookies")

    # Streaming configuration
    enable_response_streaming: bool = Field(default=False, description="Enable token-level response streaming in chat")

    # Logging configuration
    log_level: str = Field(..., description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    log_file_path: str = Field(..., description="File path for log output (empty string means no file handler)")
    seq_url: str = Field(default="", description="Seq dashboard URL for documentation/reference")
    seq_password: str = Field(default="", description="Seq admin password (empty = no auth)")
    seq_ingestion_url: str = Field(default="", description="Seq CLEF ingestion endpoint URL (Docker-internal, e.g. http://seq/api/events/raw)")

    # Spec A — compliance hardening
    hard_cap_per_receipt_sgd: float = 5000.0
    hard_cap_per_claim_sgd: float = 10000.0
    hard_cap_per_employee_per_month_sgd: float = 20000.0
    soft_cap_multiplier: float = 1.5

    compliance_critique_enabled: bool = True
    compliance_critique_model: Optional[str] = None   # None → fall back to openrouter_fallback_model_llm
    compliance_critique_temperature: float = 0.0

    # Spec A — abuse boundaries (B1, B8)
    max_justification_chars: int = 500
    max_message_chars: int = 2000
    rate_limit_messages_per_min: int = 20
    quota_submissions_per_day: int = 20
    quota_retries_per_hour: int = 5

    @property
    def postgres_dsn(self) -> str:
        """Build PostgreSQL connection string from individual fields."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn_async(self) -> str:
        """Build async PostgreSQL connection string for SQLAlchemy async engine."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def qdrant_url(self) -> str:
        """Build Qdrant URL from host and port."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


# ---------------------------------------------------------------------------
# Runtime model overrides — set via the /policies/models UI
# Persisted to a JSON file on a mounted volume so they survive container restarts.
# ---------------------------------------------------------------------------

_MODEL_OVERRIDE_FILE = Path("/usr/local/lib/python3.11/policy/system/.model_overrides.json")
_MODEL_OVERRIDE_FILE_LOCAL = Path(__file__).parent.parent.parent.parent / "policy" / "system" / ".model_overrides.json"
_modelOverrides: dict[str, str] = {}


def _overridePath() -> Path:
    """Return whichever override file path exists (Docker mount or local dev)."""
    return _MODEL_OVERRIDE_FILE if _MODEL_OVERRIDE_FILE.parent.exists() else _MODEL_OVERRIDE_FILE_LOCAL


def _loadOverrides() -> None:
    """Load persisted model overrides from disk into module dict."""
    p = _overridePath()
    if p.exists():
        try:
            _modelOverrides.update(json.loads(p.read_text()))
        except Exception:
            pass


# Load on import so overrides survive container restarts
_loadOverrides()


def setModelOverride(llm: str | None = None, vlm: str | None = None) -> None:
    """Override active LLM/VLM model at runtime. Persists to disk."""
    if llm is not None:
        _modelOverrides["llm"] = llm
    if vlm is not None:
        _modelOverrides["vlm"] = vlm
    try:
        p = _overridePath()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_modelOverrides))
    except Exception:
        pass


def getSettings() -> Settings:
    """Create and return a Settings instance, applying any runtime model overrides."""
    s = Settings()
    if "llm" in _modelOverrides:
        object.__setattr__(s, "openrouter_model_llm", _modelOverrides["llm"])
    if "vlm" in _modelOverrides:
        object.__setattr__(s, "openrouter_model_vlm", _modelOverrides["vlm"])
    return s
