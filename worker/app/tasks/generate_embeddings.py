"""Embedding generation task — generates embeddings for chunks and upserts to Qdrant."""

from uuid import UUID

from ..pipeline.embedder import Embedder


async def generate_embeddings(ctx: dict, chunk_ids: list[str]) -> dict:
    """Generate embeddings for a batch of text chunks and upsert to vector store.

    Used for re-embedding specific chunks (e.g., after OCR correction).
    The main ingestion pipeline embeds inline via ingest_manual.

    Args:
        chunk_ids: List of chunk UUIDs to embed.
    """
    pool = ctx["pool"]
    config = ctx["config"]

    # Fetch chunks from database with their page and manual context
    chunks = []
    async with pool.acquire() as conn:
        for chunk_id in chunk_ids:
            row = await conn.fetchrow(
                """
                SELECT c.id, c.chunk_text, c.chunk_index, c.page_id,
                       p.page_number, p.classification, p.manual_id,
                       m.tenant_id
                FROM chunks c
                JOIN pages p ON c.page_id = p.id
                JOIN manuals m ON p.manual_id = m.id
                WHERE c.id = $1
                """,
                UUID(chunk_id),
            )
            if row:
                chunks.append({
                    "chunk_id": str(row["id"]),
                    "chunk_text": row["chunk_text"],
                    "chunk_index": row["chunk_index"],
                    "page_id": str(row["page_id"]),
                    "page_number": row["page_number"],
                    "classification": row["classification"],
                    "manual_id": str(row["manual_id"]),
                    "tenant_id": str(row["tenant_id"]),
                })

    if not chunks:
        return {"status": "ok", "count": 0}

    # Group by manual for efficient embedding
    by_manual: dict[str, list[dict]] = {}
    for chunk in chunks:
        key = (chunk["manual_id"], chunk["tenant_id"])
        by_manual.setdefault(key, []).append(chunk)

    embedder = Embedder(
        qdrant=ctx["qdrant"],
        together_api_key=ctx["together_api_key"],
        batch_size=config.EMBED_BATCH_SIZE,
    )

    total = 0
    for (manual_id, tenant_id), manual_chunks in by_manual.items():
        results = await embedder.embed_and_store(
            chunks=manual_chunks,
            collection=ctx["collection_name"],
            tenant_id=tenant_id,
            manual_id=manual_id,
        )

        # Update vector_id on chunks
        async with pool.acquire() as conn:
            for vr in results:
                await conn.execute(
                    "UPDATE chunks SET vector_id = $1 WHERE id = $2",
                    vr["vector_id"],
                    UUID(vr["chunk_id"]),
                )

        total += len(results)

    return {"status": "ok", "count": total}
