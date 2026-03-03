"""Confidence scoring service (Phase 6)."""


class ConfidenceService:
    """Handles per-claim confidence scoring with source attribution."""

    async def score_response(self, pool, tenant_id, query_id, response_text, sources):
        raise NotImplementedError("Phase 6")

    async def get_claim_breakdown(self, pool, tenant_id, query_id):
        raise NotImplementedError("Phase 6")

    async def aggregate_confidence(self, claims):
        raise NotImplementedError("Phase 6")
