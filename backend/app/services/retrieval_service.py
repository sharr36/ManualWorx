"""Vector retrieval service (Phase 1)."""


class RetrievalService:
    """Handles embedding queries and searching the vector store."""

    async def retrieve_pages(self, pool, tenant_id, query_text, manual_ids=None, top_k=10):
        raise NotImplementedError("Phase 1")

    async def retrieve_chunks(self, pool, tenant_id, query_text, manual_ids=None, top_k=20):
        raise NotImplementedError("Phase 1")
