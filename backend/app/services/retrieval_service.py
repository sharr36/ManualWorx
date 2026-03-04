"""Vector retrieval service — embeds queries and searches Qdrant."""

import logging
import re
from uuid import UUID

logger = logging.getLogger(__name__)

import asyncpg

from ..config import settings
from ..database import set_tenant_context
from ..providers import get_embedding_provider, get_vector_provider
from .ai_service import AIService

COLLECTION_NAME = "manualworx_chunks"

# Patterns that indicate specific technical values worth boosting
KEYWORD_PATTERNS = [
    re.compile(r"\b\d+\s*(?:nm|n·m|ft[·-]?lb|lb[·-]?ft|psi|bar|kpa|mpa)\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]{1,4}[-]?\d{3,}\b"),  # Part numbers like RE505670, 4T-6789
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:mm|cm|in|inch|inches|thou)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:°[CF]|deg)\b", re.IGNORECASE),
]


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

        # Fetch full chunk + page data from DB (batch query)
        chunk_ids = [r.payload.get("chunk_id") for r in results]
        score_map = {r.payload.get("chunk_id"): r.score for r in results}

        enriched = []
        try:
            chunk_uuids = [UUID(cid) for cid in chunk_ids if cid]
        except (ValueError, TypeError) as e:
            logger.warning("Invalid chunk IDs from Qdrant: %s", e)
            return []

        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            rows = await conn.fetch(
                """
                SELECT c.id as chunk_id, c.chunk_text, c.chunk_index,
                       p.id as page_id, p.page_number, p.classification,
                       p.has_table, p.has_diagram, p.extracted_text,
                       m.id as manual_id, m.title as manual_title
                FROM chunks c
                JOIN pages p ON c.page_id = p.id
                JOIN manuals m ON p.manual_id = m.id
                WHERE c.id = ANY($1::uuid[])
                """,
                chunk_uuids,
            )
            row_map = {str(r["chunk_id"]): r for r in rows}

        for chunk_id in chunk_ids:
            row = row_map.get(chunk_id)
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

    async def retrieve_with_rerank(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        query_text: str,
        manual_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Hybrid retrieval: semantic search + keyword boost + Claude re-ranking.

        1. Over-fetch from Qdrant (RERANK_TOP_K results)
        2. Boost scores for chunks containing exact keyword matches
        3. Re-rank top candidates using Claude
        4. Deduplicate by page, return top_k
        """
        # Step 1: Get initial results (over-fetch for re-ranking)
        fetch_k = settings.RERANK_TOP_K if settings.RERANK_ENABLED else top_k
        chunks = await self.retrieve_chunks(
            pool, tenant_id, query_text, manual_ids, top_k=fetch_k
        )

        if not chunks:
            return []

        # Step 2: Keyword boost
        keywords = self._extract_keywords(query_text)
        if keywords:
            for chunk in chunks:
                text_lower = chunk.get("chunk_text", "").lower()
                boost = sum(
                    0.05 for kw in keywords if kw.lower() in text_lower
                )
                chunk["score"] = min(chunk.get("score", 0) + boost, 1.0)
            chunks.sort(key=lambda x: x["score"], reverse=True)

        if not settings.RERANK_ENABLED:
            return chunks[:top_k]

        # Step 3: Re-rank using Claude
        ai = AIService()
        reranked = await ai.rerank_passages(query_text, chunks[:settings.RERANK_TOP_K])

        # Step 4: Deduplicate by page — keep highest-scoring chunk per page
        seen_pages = {}
        for chunk in reranked:
            pid = chunk["page_id"]
            if pid not in seen_pages or chunk.get("score", 0) > seen_pages[pid].get("score", 0):
                seen_pages[pid] = chunk

        result = sorted(seen_pages.values(), key=lambda x: x.get("score", 0), reverse=True)
        return result[:top_k]

    def _extract_keywords(self, query: str) -> list[str]:
        """Extract technical keywords (part numbers, spec values) from query."""
        keywords = []
        for pattern in KEYWORD_PATTERNS:
            keywords.extend(pattern.findall(query))
        return keywords

    async def retrieve_with_diagram_context(
        self,
        pool: asyncpg.Pool,
        tenant_id: UUID,
        query_text: str,
        manual_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Diagram-aware retrieval: boosts schematic pages and enriches with annotation data."""
        import json as _json

        if settings.RERANK_ENABLED:
            chunks = await self.retrieve_with_rerank(
                pool, tenant_id, query_text, manual_ids, top_k=top_k
            )
        else:
            chunks = await self.retrieve_chunks(
                pool, tenant_id, query_text, manual_ids, top_k=top_k * 2
            )

        diagram_classifications = {
            "hydraulic_schematic", "electrical_diagram",
            "wiring_harness", "diagnostic_flowchart",
        }

        for chunk in chunks:
            cls = chunk.get("classification", "")
            if cls in diagram_classifications:
                chunk["score"] = min(chunk.get("score", 0) + 0.15, 1.0)
            if chunk.get("has_diagram"):
                chunk["score"] = min(chunk.get("score", 0) + 0.05, 1.0)

        chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        chunks = chunks[:top_k]

        # Enrich with diagram annotation data
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            for chunk in chunks:
                cls = chunk.get("classification", "")
                if cls in diagram_classifications or chunk.get("has_diagram"):
                    try:
                        ann = await conn.fetchrow(
                            """SELECT annotation_data, operating_states
                               FROM diagram_annotations
                               WHERE page_id = $1 AND tenant_id = $2""",
                            UUID(chunk["page_id"]),
                            tenant_id,
                        )
                        if ann:
                            ad = ann["annotation_data"]
                            chunk["annotation_data"] = _json.loads(ad) if isinstance(ad, str) else ad
                            os_data = ann["operating_states"]
                            chunk["operating_states"] = (_json.loads(os_data) if isinstance(os_data, str) else os_data) or []
                    except Exception as e:
                        logger.debug("Failed to load diagram annotation for page %s: %s", chunk["page_id"], e)

        return chunks

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
