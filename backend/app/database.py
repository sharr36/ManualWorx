"""Database connection pool and migration utilities."""

import asyncio
import logging
import os
from pathlib import Path
from uuid import UUID

import asyncpg

from .config import settings

logger = logging.getLogger(__name__)


async def create_pool(
    max_retries: int = 5,
    base_delay: float = 2.0,
) -> asyncpg.Pool:
    """Create the asyncpg connection pool with retry logic.

    Fly.io Postgres instances (especially hobby plans) can take time to wake
    up. Retrying with exponential backoff prevents the app from crash-looping.
    """
    last_err: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            pool = await asyncio.wait_for(
                asyncpg.create_pool(
                    settings.DATABASE_URL,
                    min_size=2,
                    max_size=20,
                    ssl=False,
                ),
                timeout=30,
            )
            if attempt > 1:
                logger.info("Database connected on attempt %d", attempt)
            return pool
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))  # 2, 4, 8, 16, 32
                logger.warning(
                    "Database connection attempt %d/%d failed: %s. Retrying in %.0fs...",
                    attempt, max_retries, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Database connection failed after %d attempts: %s",
                    max_retries, e,
                )

    raise last_err  # type: ignore[misc]


async def set_tenant_context(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    """Set the tenant context for RLS on a connection."""
    await conn.execute(
        "SELECT set_config('app.current_tenant_id', $1, true)",
        str(tenant_id),
    )


async def clear_tenant_context(conn: asyncpg.Connection) -> None:
    """Clear the tenant context (for superuser operations)."""
    await conn.execute(
        "SELECT set_config('app.current_tenant_id', '', true)"
    )


async def run_migrations(pool: asyncpg.Pool) -> None:
    """Run SQL migration files in order.

    Tracks applied migrations in _migrations table to ensure idempotency.
    """
    migrations_dir = Path(__file__).parent.parent / "migrations"
    if not migrations_dir.exists():
        return

    async with pool.acquire() as conn:
        # Create migrations tracking table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Get already applied migrations
        applied = set()
        rows = await conn.fetch("SELECT filename FROM _migrations")
        for row in rows:
            applied.add(row["filename"])

        # Apply pending migrations in order
        migration_files = sorted(
            f for f in os.listdir(migrations_dir)
            if f.endswith(".sql") and f != "__init__.py"
        )

        for filename in migration_files:
            if filename in applied:
                continue

            sql = (migrations_dir / filename).read_text()
            try:
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO _migrations (filename) VALUES ($1)",
                    filename,
                )
                print(f"  Applied migration: {filename}")
            except Exception as e:
                print(f"  FAILED migration: {filename} — {e}")
                raise
