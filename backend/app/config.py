"""Application configuration loaded from environment variables."""

import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_INSECURE_SECRET = "change-me-to-a-random-secret-at-least-32-chars"


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://manualworx:password@localhost:5432/manualworx"
    REDIS_URL: str = "redis://localhost:6379"
    QDRANT_URL: str = "http://localhost:6333"

    # AI
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_MODEL: str = "claude-sonnet-4-5-20250929"
    ESCALATION_MODEL: str = "claude-opus-4-5-20250120"

    # Object storage (Tigris / S3-compatible)
    AWS_ENDPOINT_URL_S3: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    BUCKET_NAME: str = "manualworx"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER_MONTHLY: str = ""
    STRIPE_PRICE_PRO_MONTHLY: str = ""
    STRIPE_PRICE_SHOP_BASE_MONTHLY: str = ""
    STRIPE_PRICE_SHOP_PER_USER_MONTHLY: str = ""

    # OCR
    OCR_PROVIDER: str = "tesseract"  # tesseract | claude_vision | unstructured | reducto | pymupdf
    OCR_FALLBACK_PROVIDER: str = "claude_vision"  # fallback when primary returns low confidence
    OCR_FALLBACK_THRESHOLD: float = 0.5  # confidence below this triggers fallback
    AZURE_DI_ENDPOINT: str = ""
    AZURE_DI_KEY: str = ""
    UNSTRUCTURED_API_URL: str = ""  # e.g. http://manualworx-unstructured.flycast:8000
    UNSTRUCTURED_API_KEY: str = ""
    REDUCTO_API_KEY: str = ""
    CLAUDE_VISION_MODEL: str = "claude-haiku-4-5-20251001"  # model for vision OCR

    # Embeddings
    EMBEDDING_PROVIDER: str = "together"
    EMBEDDING_SERVICE_URL: str = ""
    TOGETHER_API_KEY: str = ""

    # Vector
    COLLECTION_NAME: str = "manualworx_chunks"
    EMBEDDING_DIMENSION: int = 1024

    # App
    SECRET_KEY: str = _INSECURE_SECRET
    CORS_ORIGINS: str = "http://localhost:3000"
    MAX_PAGES_PER_QUERY: int = 10
    STREAM_RESPONSES: bool = True
    LOG_LEVEL: str = "INFO"

    # Re-ranking
    RERANK_ENABLED: bool = True
    RERANK_TOP_K: int = 40
    RERANK_FINAL_K: int = 10
    RERANK_MODEL: str = "claude-haiku-4-5-20251001"

    # Schematic Viewer
    SYMBOL_LIBRARY_PATH: str = "/app/assets/symbols/"
    ANNOTATION_CACHE_TTL: int = 86400

    # Super Admin
    SUPERADMIN_EMAILS: str = ""  # comma-separated emails with superadmin access

    @model_validator(mode="after")
    def _validate_critical_settings(self) -> "Settings":
        """Warn on missing critical config; fail on insecure SECRET_KEY in production."""
        warnings: list[str] = []
        if not self.ANTHROPIC_API_KEY:
            warnings.append("ANTHROPIC_API_KEY is not set — AI features will fail")
        if not self.TOGETHER_API_KEY:
            warnings.append("TOGETHER_API_KEY is not set — embedding/search will fail")
        if not self.STRIPE_SECRET_KEY:
            warnings.append("STRIPE_SECRET_KEY is not set — billing will be disabled")
        if self.SECRET_KEY == _INSECURE_SECRET:
            warnings.append(
                "SECRET_KEY is using the insecure default — set a strong random value in production"
            )
        for msg in warnings:
            logger.warning("CONFIG: %s", msg)
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def superadmin_email_set(self) -> set[str]:
        if not self.SUPERADMIN_EMAILS:
            return set()
        return {e.strip().lower() for e in self.SUPERADMIN_EMAILS.split(",") if e.strip()}

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
