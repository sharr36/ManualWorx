"""Vector retrieval service — embeds queries and searches Qdrant."""

from uuid import UUID

import asyncpg

from ..database import set_tenant_context
from ..providers import get_embedding_provider, get_vector_provider

COLLECTION_NAME = "manualworx_chunks"


class RetrievalService:
    """Handles embedding queries and searching the vector store."""

    async def retrieve_chunks(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        query_text: str,
        manual_ids: list[str] | None = None,
        top_k: int = 20,
    ) -> list[dict]:
        """Embed query, search Qdrant, fetch chunk/page details from DB.

        Returns:
            List of {chunk_id, page_id, page_number, chunk_text, classification,
                     score, manual_id, manual_title, has_table, has_diagram}.
        """
        # Embed query
        embedding = get_embedding_provider()
        query_vector = await embedding.embed_text(query_text)

        # Build Qdrant filter
        filter_dict = {"tenant_id": str(tenant_id)}

        # Search Qdrant (over-fetch for manual_id filtering)
        vector = get_vector_provider()
        results = await vector.search(
            collection=COLLECTION_NAME,
            vector=query_vector,
            filter=filter_dict,
            top_k=top_k * 2,
        )

        # Filter by manual_ids if specified
        if manual_ids:
            manual_id_set = set(manual_ids)
            results = [
                r for r in results if r.payload.get("manual_id") in manual_id_set
            ]

        results = results[:top_k]
        if not results:
            return []

        # Fetch full chunk + page data from DB
        chunk_ids = [r.payload.get("chunk_id") for r in results]
        score_map = {r.payload.get("chunk_id"): r.score for r in results}

        enriched = []
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            for chunk_id in chunk_ids:
                try:
                    row = await conn.fetchrow(
                        """
                        SELECT c.id as chunk_id, c.chunk_text, c.chunk_index,
                               p.id as page_id, p.page_number, p.classification,
                               p.has_table, p.has_diagram, p.extracted_text,
                               m.id as manual_id, m.title as manual_title
                        FROM chunks c
                        JOIN pages p ON c.page_id = p.id
                        JOIN manuals m ON p.manual_id = m.id
                        WHERE c.id = $1
                        """,
                        UUID(chunk_id),
                    )
                except Exception:
                    continue

                if row:
                    enriched.append({
                        "chunk_id": str(row["chunk_id"]),
                        "page_id": str(row["page_id"]),
                        "page_number": row["page_number"],
                        "chunk_text": row["chunk_text"],
                        "chunk_index": row["chunk_index"],
                        "classification": row["classification"],
                        "has_table": row["has_table"],
                        "has_diagram": row["has_diagram"],
                        "manual_id": str(row["manual_id"]),
                        "manual_title": row["manual_title"],
                        "score": score_map.get(chunk_id, 0.0),
                        "full_page_text": row["extracted_text"],
                    })

        enriched.sort(key=lambda x: x["score"], reverse=True)
        return enriched

    async def retrieve_pages(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        query_text: str,
        manual_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Retrieve unique pages (deduplicated from chunk results)."""
        chunks = await self.retrieve_chunks(
            pool, tenant_id, query_text, manual_ids, top_k=top_k * 3
        )

        seen = {}
        for chunk in chunks:
            pid = chunk["page_id"]
            if pid not in seen or chunk["score"] > seen[pid]["score"]:
                seen[pid] = chunk

        pages = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
        return pages[:top_k]
