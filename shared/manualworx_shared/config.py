"""Base configuration shared across all ManualWorx services."""

from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    """Base configuration that all services inherit from."""

    DATABASE_URL: str = "postgresql://manualworx:password@localhost:5432/manualworx"
    REDIS_URL: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
