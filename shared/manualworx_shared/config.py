"""Base configuration shared across all ManualWorx services."""

import logging
from urllib.parse import urlparse

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class BaseConfig(BaseSettings):
    """Base configuration that all services inherit from."""

    DATABASE_URL: str = "postgresql://manualworx:password@localhost:5432/manualworx"
    REDIS_URL: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def arq_redis_settings(url: str):
    """Create arq RedisSettings from a Redis URL string.

    Handles standard redis:// / rediss:// and non-standard schemes from
    managed providers (Upstash, Fly, etc.).
    """
    from arq.connections import RedisSettings

    parsed = urlparse(url)
    if parsed.scheme in ("redis", "rediss", "unix"):
        try:
            return RedisSettings.from_dsn(url)
        except RuntimeError:
            pass  # Fall through to manual parsing

    ssl = parsed.scheme in ("rediss",) or "tls" in parsed.scheme
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    password = parsed.password
    database = 0
    if parsed.path and parsed.path.strip("/").isdigit():
        database = int(parsed.path.strip("/"))

    logger.info("Parsed Redis URL manually: host=%s port=%d ssl=%s", host, port, ssl)
    return RedisSettings(host=host, port=port, password=password, database=database, ssl=ssl)
