"""Query orchestration service (Phase 1)."""


class QueryService:
    """Orchestrates retrieval, AI reasoning, and response generation."""

    async def create_query(self, pool, tenant_id, query_text, query_mode, manual_ids=None):
        raise NotImplementedError("Phase 1")

    async def followup_query(self, pool, tenant_id, query_id, query_text):
        raise NotImplementedError("Phase 1")

    async def get_query(self, pool, tenant_id, query_id):
        raise NotImplementedError("Phase 1")
