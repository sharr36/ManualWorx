"""Re-chunk a manual — deletes existing chunks, re-chunks from page text, and embeds."""

import asyncio
import logging
from uuid import UUID

from ..pipeline.chunker import Chunker
from ..pipeline.embedder import Embedder

logger = logging.getLogger(__name__)


async def rechunk_manual(ctx: dict, manual_id: str) -> dict:
    """Delete existing chunks, re-chunk from page extracted_text, and embed.

    Use when pages exist with text but chunking produced too few chunks
    (e.g., original ingestion had issues).
    """
    pool = ctx["pool"]
    config = ctx["config"]

    logger.info("[%s] Starting rechunk", manual_id[:8])

    # 1. Get manual info
    async with pool.acquire() as conn:
        manual = await conn.fetchrow(
            "SELECT id, tenant_id FROM manuals WHERE id = $1", UUID(manual_id)
        )
    if not manual:
        return {"status": "error", "error": "Manual not found"}

    tenant_id = str(manual["tenant_id"])

    # 2. Fetch all pages with text
    async with pool.acquire() as conn:
        pages = await conn.fetch(
            """SELECT id, page_number, extracted_text, classification, has_diagram
               FROM pages WHERE manual_id = $1 ORDER BY page_number""",
            UUID(manual_id),
        )

    if not pages:
        return {"status": "error", "error": "No pages found"}

    pages_data = [
        {
            "page_id": str(p["id"]),
            "page_number": p["page_number"],
            "text": p["extracted_text"] or "",
            "classification": p["classification"] or "text",
            "has_diagram": p["has_diagram"],
        }
        for p in pages
    ]

    pages_with_text = sum(1 for p in pages_data if p["text"].strip())
    logger.info("[%s] Found %d pages (%d with text)", manual_id[:8], len(pages_data), pages_with_text)

    # 3. Delete existing chunks (and their Qdrant vectors)
    async with pool.acquire() as conn:
        # Get vector_ids to delete from Qdrant
        vector_rows = await conn.fetch(
            """SELECT c.vector_id FROM chunks c
               JOIN pages p ON p.id = c.page_id
               WHERE p.manual_id = $1 AND c.vector_id IS NOT NULL""",
            UUID(manual_id),
        )
        old_vector_ids = [str(r["vector_id"]) for r in vector_rows]

        # Delete chunks from DB
        deleted = await conn.execute(
            """DELETE FROM chunks WHERE page_id IN (
                   SELECT id FROM pages WHERE manual_id = $1
               )""",
            UUID(manual_id),
        )
        logger.info("[%s] Deleted old chunks: %s", manual_id[:8], deleted)

    # Delete old vectors from Qdrant
    if old_vector_ids and ctx.get("qdrant") is not None:
        try:
            from qdrant_client.models import PointIdsList
            await ctx["qdrant"].delete(
                collection_name=ctx["collection_name"],
                points_selector=PointIdsList(points=old_vector_ids),
            )
            logger.info("[%s] Deleted %d old vectors from Qdrant", manual_id[:8], len(old_vector_ids))
        except Exception as e:
            logger.warning("[%s] Failed to delete old Qdrant vectors: %s", manual_id[:8], e)

    # 4. Re-chunk
    chunker = Chunker(chunk_size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP)
    all_chunks = chunker.chunk_manual(pages_data)
    logger.info("[%s] Created %d chunks from %d pages", manual_id[:8], len(all_chunks), len(pages_data))

    if not all_chunks:
        return {"status": "no_chunks", "manual_id": manual_id, "pages": len(pages_data)}

    # 5. Insert chunks
    chunk_records = []
    async with pool.acquire() as conn:
        for chunk in all_chunks:
            row = await conn.fetchrow(
                """INSERT INTO chunks (page_id, chunk_index, chunk_text, token_count)
                   VALUES ($1, $2, $3, $4)
                   RETURNING id""",
                UUID(chunk["page_id"]),
                chunk["chunk_index"],
                chunk["chunk_text"],
                chunk["token_count"],
            )
            chunk["chunk_id"] = str(row["id"])
            chunk_records.append(chunk)

    # 6. Embed all chunks
    embedded = 0
    if chunk_records and ctx.get("qdrant") is not None:
        logger.info("[%s] Embedding %d chunks", manual_id[:8], len(chunk_records))
        try:
            embedder = Embedder(
                qdrant=ctx["qdrant"],
                together_api_key=ctx["together_api_key"],
                batch_size=config.EMBED_BATCH_SIZE,
            )
            vector_results = await asyncio.wait_for(
                embedder.embed_and_store(
                    chunks=chunk_records,
                    collection=ctx["collection_name"],
                    tenant_id=tenant_id,
                    manual_id=manual_id,
                ),
                timeout=600,
            )
            async with pool.acquire() as conn:
                for vr in vector_results:
                    await conn.execute(
                        "UPDATE chunks SET vector_id = $1 WHERE id = $2",
                        vr["vector_id"],
                        UUID(vr["chunk_id"]),
                    )
            embedded = len(vector_results)
            logger.info("[%s] Embedded %d chunks", manual_id[:8], embedded)
        except Exception as e:
            logger.error("[%s] Embedding failed (non-fatal): %s", manual_id[:8], e)
    else:
        logger.warning("[%s] Skipping embedding — Qdrant not available", manual_id[:8])

    return {
        "status": "ok",
        "manual_id": manual_id,
        "pages": len(pages_data),
        "pages_with_text": pages_with_text,
        "chunks_created": len(chunk_records),
        "chunks_embedded": embedded,
    }
