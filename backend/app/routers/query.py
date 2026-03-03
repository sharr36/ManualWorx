"""Query and chat endpoints (Phase 1)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..models.query import FollowupRequest, QueryRequest

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("")
async def create_query(body: QueryRequest) -> dict:
    """Submit a natural language query against manuals."""
    raise HTTPException(status_code=501, detail="Query engine coming in Phase 1")


@router.post("/{query_id}/followup")
async def followup_query(query_id: UUID, body: FollowupRequest) -> dict:
    """Submit a follow-up question in the same context."""
    raise HTTPException(status_code=501, detail="Follow-up queries coming in Phase 1")


@router.get("/{query_id}")
async def get_query(query_id: UUID) -> dict:
    """Retrieve a query and its response."""
    raise HTTPException(status_code=501, detail="Query retrieval coming in Phase 1")
