"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


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

    # OCR (optional)
    AZURE_DI_ENDPOINT: str = ""
    AZURE_DI_KEY: str = ""

    # Embeddings
    EMBEDDING_PROVIDER: str = "together"
    EMBEDDING_SERVICE_URL: str = ""
    TOGETHER_API_KEY: str = ""

    # Vector
    COLLECTION_NAME: str = "manualworx_chunks"
    EMBEDDING_DIMENSION: int = 768

    # App
    SECRET_KEY: str = "change-me-to-a-random-secret-at-least-32-chars"
    CORS_ORIGINS: str = "http://localhost:3000"
    MAX_PAGES_PER_QUERY: int = 10
    STREAM_RESPONSES: bool = True

    # Re-ranking
    RERANK_ENABLED: bool = True
    RERANK_TOP_K: int = 40
    RERANK_FINAL_K: int = 10
    RERANK_MODEL: str = "claude-haiku-4-5-20251001"

    # Schematic Viewer
    SYMBOL_LIBRARY_PATH: str = "/app/assets/symbols/"
    ANNOTATION_CACHE_TTL: int = 86400

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
