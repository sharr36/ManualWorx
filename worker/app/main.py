"""arq worker entry point."""

import asyncio
import logging

import asyncpg
import boto3
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from manualworx_shared.config import arq_redis_settings

from .config import WorkerSettings as Config
from .tasks.annotate_diagram import annotate_diagram
from .tasks.classify_pages import classify_pages
from .tasks.generate_embeddings import generate_embeddings
from .tasks.generate_learning_path import generate_learning_path
from .tasks.ingest_manual import ingest_manual
from .tasks.process_page import process_page

logger = logging.getLogger(__name__)

_config = Config()

_DB_CONNECT_MAX_RETRIES = 5
_DB_CONNECT_BASE_DELAY = 2  # seconds


async def on_startup(ctx: dict) -> None:
    """Initialize shared resources for all worker tasks."""
    # Database pool
    dsn = _config.DATABASE_URL
    if not dsn or not dsn.startswith(("postgresql://", "postgres://")):
        scheme = repr(dsn.split("://")[0]) if "://" in dsn else "<empty>"
        raise RuntimeError(
            "DATABASE_URL is missing or invalid (got scheme %s). "
            "Set a valid postgresql:// connection string." % scheme
        )

    # Fly internal Postgres does not use SSL
    use_ssl: object = False
    if "sslmode=" not in dsn:
        use_ssl = False

    for attempt in range(1, _DB_CONNECT_MAX_RETRIES + 1):
        try:
            ctx["pool"] = await asyncpg.create_pool(
                dsn, min_size=2, max_size=10, ssl=use_ssl
            )
            break
        except (
            ConnectionResetError,
            ConnectionRefusedError,
            OSError,
            asyncpg.InterfaceError,
        ) as exc:
            if attempt == _DB_CONNECT_MAX_RETRIES:
                raise
            delay = _DB_CONNECT_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Database connection attempt %d/%d failed: %s. "
                "Retrying in %ds...",
                attempt,
                _DB_CONNECT_MAX_RETRIES,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    # Qdrant client + ensure collection exists (optional — degrade gracefully)
    ctx["qdrant"] = None
    for attempt in range(1, _DB_CONNECT_MAX_RETRIES + 1):
        try:
            client = AsyncQdrantClient(url=_config.QDRANT_URL)
            collections = await client.get_collections()
            existing = {c.name for c in collections.collections}
            if _config.COLLECTION_NAME not in existing:
                await client.create_collection(
                    collection_name=_config.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=_config.EMBEDDING_DIMENSION, distance=Distance.COSINE
                    ),
                )
            ctx["qdrant"] = client
            break
        except Exception as exc:
            if attempt == _DB_CONNECT_MAX_RETRIES:
                logger.warning(
                    "Qdrant unavailable after %d attempts: %s. "
                    "Worker will start without vector search — "
                    "embedding/search tasks will fail until Qdrant is reachable.",
                    _DB_CONNECT_MAX_RETRIES,
                    exc,
                )
                break
            delay = _DB_CONNECT_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Qdrant connection attempt %d/%d failed: %s. "
                "Retrying in %ds...",
                attempt,
                _DB_CONNECT_MAX_RETRIES,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    # S3/Tigris storage client
    ctx["s3"] = boto3.client(
        "s3",
        endpoint_url=_config.AWS_ENDPOINT_URL_S3,
        aws_access_key_id=_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=_config.AWS_SECRET_ACCESS_KEY,
    )
    ctx["bucket"] = _config.BUCKET_NAME

    # Embedding config
    ctx["together_api_key"] = _config.TOGETHER_API_KEY
    ctx["collection_name"] = _config.COLLECTION_NAME

    # arq redis reference for enqueuing sub-jobs
    ctx["redis"] = ctx.get("redis")  # arq injects this automatically

    # Processing config
    ctx["config"] = _config


async def on_shutdown(ctx: dict) -> None:
    """Clean up shared resources."""
    if "pool" in ctx:
        await ctx["pool"].close()
    if "qdrant" in ctx:
        await ctx["qdrant"].close()


class WorkerSettings:
    """arq worker settings."""

    functions = [
        ingest_manual,
        process_page,
        generate_embeddings,
        classify_pages,
        annotate_diagram,
        generate_learning_path,
    ]

    on_startup = on_startup
    on_shutdown = on_shutdown

    redis_settings = arq_redis_settings(_config.REDIS_URL)

    max_jobs = 10
    job_timeout = 600  # 10 minutes per job
    keep_result = 3600  # Keep results for 1 hour
