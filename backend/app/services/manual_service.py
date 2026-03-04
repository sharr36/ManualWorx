"""Manual management service — upload, CRUD, and status tracking."""

import logging
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

import asyncpg
from arq.connections import ArqRedis, create_pool as create_arq_pool

from ..config import settings
from ..database import set_tenant_context
from ..providers import get_storage_provider, get_vector_provider


class ManualService:
    """Handles manual upload, processing status, and metadata."""

    async def upload_manual(
        self,
        pool: asyncpg.Pool,
        redis: ArqRedis | None,
        tenant_id: UUID,
        title: str,
        make: str | None,
        model: str | None,
        manual_type: str,
        pdf_bytes: bytes,
        filename: str,
    ) -> dict:
        """Upload a PDF manual and enqueue it for processing.

        Returns:
            Manual record dict.
        """
        manual_id = uuid4()

        # Check manual limit
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            row = await conn.fetchrow(
                "SELECT manual_limit FROM tenants WHERE id = $1", tenant_id
            )
            if row:
                current = await conn.fetchval(
                    "SELECT COUNT(*) FROM manuals WHERE tenant_id = $1",
                    tenant_id,
                )
                if row["manual_limit"] > 0 and current >= row["manual_limit"]:
                    raise ValueError("Manual limit reached for your plan")

        # Upload PDF to storage
        storage = get_storage_provider()
        storage_key = f"manuals/{tenant_id}/{manual_id}/original.pdf"
        await storage.upload(storage_key, pdf_bytes, "application/pdf")

        # Insert manual record
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            row = await conn.fetchrow(
                """
                INSERT INTO manuals (id, tenant_id, title, make, model, manual_type,
                                     upload_status, original_pdf_url)
                VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)
                RETURNING id, tenant_id, title, make, model, manual_type, total_pages,
                          upload_status, visibility, original_pdf_url, created_at, updated_at
                """,
                manual_id,
                tenant_id,
                title,
                make,
                model,
                manual_type,
                storage_key,
            )

        # Enqueue ingestion job
        if redis:
            arq_pool = await create_arq_pool(redis.connection_pool)
            await arq_pool.enqueue_job(
                "ingest_manual",
                str(manual_id),
                str(tenant_id),
            )
        else:
            # Fallback: create a new arq connection
            from arq.connections import RedisSettings

            arq_pool = await create_arq_pool(
                RedisSettings.from_dsn(settings.REDIS_URL)
            )
            await arq_pool.enqueue_job(
                "ingest_manual",
                str(manual_id),
                str(tenant_id),
            )
            await arq_pool.close()

        return _row_to_dict(row)

    async def get_manual(
        self, pool: asyncpg.Pool, tenant_id: UUID, manual_id: UUID
    ) -> dict | None:
        """Get a single manual with page stats."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            row = await conn.fetchrow(
                """
                SELECT m.id, m.tenant_id, m.title, m.make, m.model, m.manual_type,
                       m.total_pages, m.upload_status, m.visibility, m.original_pdf_url,
                       m.created_at, m.updated_at,
                       COUNT(p.id) FILTER (WHERE p.id IS NOT NULL) as pages_processed
                FROM manuals m
                LEFT JOIN pages p ON p.manual_id = m.id
                WHERE m.id = $1 AND m.tenant_id = $2
                GROUP BY m.id
                """,
                manual_id,
                tenant_id,
            )
        if not row:
            return None
        result = _row_to_dict(row)
        result["pages_processed"] = row["pages_processed"]
        return result

    async def get_manual_pages(
        self, pool: asyncpg.Pool, tenant_id: UUID, manual_id: UUID
    ) -> list[dict]:
        """Get all pages for a manual."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            # Verify manual belongs to tenant
            exists = await conn.fetchval(
                "SELECT 1 FROM manuals WHERE id = $1 AND tenant_id = $2",
                manual_id,
                tenant_id,
            )
            if not exists:
                return []

            rows = await conn.fetch(
                """
                SELECT id, manual_id, page_number, classification, extracted_text,
                       image_url, has_table, has_diagram
                FROM pages
                WHERE manual_id = $1
                ORDER BY page_number
                """,
                manual_id,
            )
        return [dict(r) for r in rows]

    async def list_manuals(
        self, pool: asyncpg.Pool, tenant_id: UUID
    ) -> list[dict]:
        """List all manuals for a tenant."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            rows = await conn.fetch(
                """
                SELECT id, tenant_id, title, make, model, manual_type, total_pages,
                       upload_status, visibility, created_at, updated_at
                FROM manuals
                WHERE tenant_id = $1
                ORDER BY created_at DESC
                """,
                tenant_id,
            )
        return [_row_to_dict(r) for r in rows]

    async def delete_manual(
        self, pool: asyncpg.Pool, tenant_id: UUID, manual_id: UUID
    ) -> bool:
        """Delete a manual and its associated data."""
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)

            # Get the manual to find storage keys
            row = await conn.fetchrow(
                "SELECT original_pdf_url FROM manuals WHERE id = $1 AND tenant_id = $2",
                manual_id,
                tenant_id,
            )
            if not row:
                return False

            # Delete from database (cascades to pages and chunks)
            await conn.execute(
                "DELETE FROM manuals WHERE id = $1 AND tenant_id = $2",
                manual_id,
                tenant_id,
            )

        # Delete vectors from Qdrant
        try:
            vector = get_vector_provider()
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            await vector.client.delete(
                collection_name=settings.COLLECTION_NAME
                if hasattr(settings, "COLLECTION_NAME")
                else "manualworx_chunks",
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="manual_id", match=MatchValue(value=str(manual_id))
                        )
                    ]
                ),
            )
        except Exception as e:
            logger.warning("Failed to delete Qdrant vectors for manual %s: %s", manual_id, e)

        # Delete from storage
        try:
            storage = get_storage_provider()
            prefix = f"manuals/{tenant_id}/{manual_id}/"
            # Delete known keys
            if row["original_pdf_url"]:
                await storage.delete(row["original_pdf_url"])
        except Exception as e:
            logger.warning("Failed to delete storage files for manual %s: %s", manual_id, e)

        return True

    async def update_processing_status(
        self,
        pool: asyncpg.Pool,
        manual_id: UUID,
        status: str,
        total_pages: int | None = None,
    ) -> None:
        """Update the processing status of a manual."""
        async with pool.acquire() as conn:
            if total_pages is not None:
                await conn.execute(
                    """
                    UPDATE manuals SET upload_status = $1, total_pages = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    status,
                    total_pages,
                    manual_id,
                )
            else:
                await conn.execute(
                    "UPDATE manuals SET upload_status = $1, updated_at = NOW() WHERE id = $2",
                    status,
                    manual_id,
                )


def _row_to_dict(row) -> dict:
    """Convert an asyncpg Record to a serializable dict."""
    d = dict(row)
    for key, val in d.items():
        if isinstance(val, UUID):
            d[key] = str(val)
        elif hasattr(val, "isoformat"):
            d[key] = val.isoformat()
    return d
