"""Database connection pool and migration utilities."""

import os
from pathlib import Path
from uuid import UUID

import asyncpg

from .config import settings


async def create_pool() -> asyncpg.Pool:
    """Create the asyncpg connection pool."""
    return await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=2,
        max_size=20,
        ssl=False,
    )


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
