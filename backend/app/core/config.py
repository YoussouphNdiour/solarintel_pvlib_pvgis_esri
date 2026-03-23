"""Application configuration loaded from environment variables.

Uses pydantic-settings for type-safe env var parsing with validation.
All sensitive values must be provided via environment — never hardcoded.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────────────
    app_name: str = "SolarIntel v2"
    app_version: str = "2.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # ── Security ─────────────────────────────────────────────────────────────
    secret_key: str = Field(
        ...,
        description="Random 64-char hex string for JWT signing.",
        min_length=32,
    )
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # ── CORS ─────────────────────────────────────────────────────────────────
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    # Render.com frontend URL — automatically added to CORS origins in production
    render_frontend_url: str | None = Field(
        default=None,
        description="Render.com static frontend URL (e.g. https://solarintel-frontend.onrender.com).",
    )

    @property
    def cors_origins(self) -> list[str]:
        """Effective CORS origins — merges allowed_origins with Render frontend URL."""
        origins = list(self.allowed_origins)
        if self.render_frontend_url and self.render_frontend_url not in origins:
            origins.append(self.render_frontend_url)
        return origins

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL async DSN (postgresql+asyncpg://...).",
    )
    database_pool_size: int = 5   # keep low for Render free tier PostgreSQL
    database_max_overflow: int = 5

    # ── Redis ────────────────────────────────────────────────────────────────
    # Optional on Render free tier — use Upstash Redis (https://upstash.com)
    # When unset: PVGIS results are fetched fresh each time (no caching),
    # JWT sessions are stateless (no server-side revocation).
    redis_url: RedisDsn | None = Field(
        default=None,
        description="Redis connection URL (redis://...). Optional — app degrades gracefully without it.",
    )

    # ── External APIs ────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(
        ...,
        description="Anthropic API key for Claude (claude-opus-4-6).",
    )
    arcgis_api_key: str | None = Field(
        default=None,
        description="ArcGIS JS SDK API key. Optional — map and satellite PDF embed disabled when absent.",
    )
    pvgis_base_url: AnyHttpUrl = Field(
        default="https://re.jrc.ec.europa.eu/api/v5_2",  # type: ignore[assignment]
        description="PVGIS REST API base URL.",
    )

    # ── PDF Generation ───────────────────────────────────────────────────────
    pdf_storage_path: str = "/tmp/solarintel/reports"
    pdf_generation_timeout_seconds: int = 60

    # ── Senelec Tariff ───────────────────────────────────────────────────────
    senelec_tariff_kwh_xof: float = Field(
        default=121.0,
        description="Senelec residential tariff in CFA Francs per kWh (2024 rate).",
    )

    # ── OAuth2 Google ─────────────────────────────────────────────────────────
    google_client_id: str | None = Field(
        default=None,
        description="Google OAuth2 client ID for social login.",
    )
    google_client_secret: str | None = Field(
        default=None,
        description="Google OAuth2 client secret for social login.",
    )

    # ── WhatsApp Business API ─────────────────────────────────────────────────
    whatsapp_token: str | None = Field(
        default=None,
        description="WhatsApp Business API bearer token.",
    )
    whatsapp_phone_id: str | None = Field(
        default=None,
        description="WhatsApp Business phone number ID for message sending.",
    )

    # ── Webhooks ──────────────────────────────────────────────────────────────
    webhook_secret: str | None = Field(
        default=None,
        description=(
            "HMAC-SHA256 secret for verifying SunSpec inverter webhook signatures. "
            "Falls back to SECRET_KEY when not set."
        ),
    )

    # ── Monitoring & Alerting ─────────────────────────────────────────────────
    sentry_dsn: str | None = Field(
        default=None,
        description="Sentry DSN for error tracking and performance monitoring.",
    )
    grafana_api_key: str | None = Field(
        default=None,
        description="Grafana API key for pushing custom metrics.",
    )

    # ── Ollama Fallback LLM ───────────────────────────────────────────────────
    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Base URL of the local Ollama inference server.",
    )
    ollama_model: str = Field(
        default="llama3",
        description="Ollama model name to use as Claude fallback.",
    )

    # ── PVGIS Cache ───────────────────────────────────────────────────────────
    pvgis_cache_ttl_days: int = Field(
        default=30,
        description="Redis TTL in days for cached PVGIS irradiance responses.",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_async_driver(cls, value: str) -> str:
        """Ensure the database URL uses the asyncpg driver."""
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def is_production(self) -> bool:
        """Return True when running in the production environment."""
        return self.environment == "production"

    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        return str(self.database_url).replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance.

    The result is cached so that environment variables are parsed only once
    per process lifetime. Use ``get_settings.cache_clear()`` in tests that
    need to override settings.
    """
    return Settings()  # type: ignore[call-arg]
