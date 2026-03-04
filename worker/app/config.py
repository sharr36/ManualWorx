"""Worker configuration."""

from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    DATABASE_URL: str = "postgresql://manualworx:password@localhost:5432/manualworx"
    REDIS_URL: str = "redis://localhost:6379"
    QDRANT_URL: str = "http://localhost:6333"

    # Storage
    AWS_ENDPOINT_URL_S3: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    BUCKET_NAME: str = "manualworx"

    # OCR
    AZURE_DI_ENDPOINT: str = ""
    AZURE_DI_KEY: str = ""

    # Embeddings
    EMBEDDING_PROVIDER: str = "together"
    EMBEDDING_SERVICE_URL: str = ""
    TOGETHER_API_KEY: str = ""

    # AI
    ANTHROPIC_API_KEY: str = ""

    # Vector
    COLLECTION_NAME: str = "manualworx_chunks"
    EMBEDDING_DIMENSION: int = 768

    # Processing
    PDF_DPI: int = 300
    MAX_CONCURRENT_PAGES: int = 4
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    EMBED_BATCH_SIZE: int = 32

    class Config:
        env_file = ".env"
