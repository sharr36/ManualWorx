"""Embedding generation task."""


async def generate_embeddings(ctx: dict, chunk_ids: list[str]) -> dict:
    """Generate embeddings for a batch of text chunks and upsert to vector store.

    Args:
        chunk_ids: List of chunk IDs to embed.
    """
    # TODO: Implement in Phase 1
    # 1. Fetch chunks from database
    # 2. Batch embed via EmbeddingProvider
    # 3. Upsert to Qdrant with tenant_id + manual_id payload
    # 4. Update chunks with vector_id
    return {"status": "not_implemented", "count": len(chunk_ids)}
