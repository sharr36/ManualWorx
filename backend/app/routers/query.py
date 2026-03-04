"""Query and chat endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..models.query import (
    ClaimResponse,
    FollowupRequest,
    QueryListItem,
    QueryRequest,
    QueryResponse,
    RefinementSuggestion,
)
from ..services.confidence_service import ConfidenceService
from ..services.query_service import QueryService

router = APIRouter(prefix="/api/query", tags=["query"])
_service = QueryService()
_confidence = ConfidenceService()


@router.post("")
async def create_query(body: QueryRequest, request: Request) -> QueryResponse:
    """Submit a natural language query against manuals."""
    pool = request.app.state.db_pool
    redis = getattr(request.app.state, "redis", None)
    tenant_id = request.state.tenant_id
    skill_level = getattr(request.state, "user_skill_level", None)

    result = await _service.create_query(
        pool=pool,
        redis=redis,
        tenant_id=tenant_id,
        query_text=body.query_text,
        query_mode=body.query_mode,
        manual_ids=body.manual_ids,
        skill_level=skill_level,
    )

    return QueryResponse(**result)


@router.post("/stream")
async def create_query_stream(body: QueryRequest, request: Request):
    """Submit a query and stream the response as SSE events."""
    pool = request.app.state.db_pool
    redis = getattr(request.app.state, "redis", None)
    tenant_id = request.state.tenant_id
    skill_level = getattr(request.state, "user_skill_level", None)

    return StreamingResponse(
        _service.create_query_stream(
            pool=pool,
            redis=redis,
            tenant_id=tenant_id,
            query_text=body.query_text,
            query_mode=body.query_mode,
            manual_ids=body.manual_ids,
            skill_level=skill_level,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{query_id}/followup")
async def followup_query(
    query_id: UUID, body: FollowupRequest, request: Request
) -> QueryResponse:
    """Submit a follow-up question in the same context."""
    pool = request.app.state.db_pool
    redis = getattr(request.app.state, "redis", None)
    tenant_id = request.state.tenant_id
    skill_level = getattr(request.state, "user_skill_level", None)

    try:
        result = await _service.followup_query(
            pool=pool,
            redis=redis,
            tenant_id=tenant_id,
            query_id=query_id,
            query_text=body.query_text,
            skill_level=skill_level,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return QueryResponse(**result)


@router.post("/{query_id}/followup/stream")
async def followup_query_stream(
    query_id: UUID, body: FollowupRequest, request: Request
):
    """Stream a follow-up query response as SSE events."""
    pool = request.app.state.db_pool
    redis = getattr(request.app.state, "redis", None)
    tenant_id = request.state.tenant_id
    skill_level = getattr(request.state, "user_skill_level", None)

    return StreamingResponse(
        _service.followup_query_stream(
            pool=pool,
            redis=redis,
            tenant_id=tenant_id,
            query_id=query_id,
            query_text=body.query_text,
            skill_level=skill_level,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history")
async def query_history(request: Request, limit: int = 20, offset: int = 0) -> list[QueryListItem]:
    """List recent queries for the current tenant."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    results = await _service.list_queries(pool, tenant_id, limit=limit, offset=offset)
    return [QueryListItem(**r) for r in results]


@router.get("/{query_id}")
async def get_query(query_id: UUID, request: Request) -> QueryResponse:
    """Retrieve a query and its response."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    result = await _service.get_query(pool, tenant_id, query_id)
    if not result:
        raise HTTPException(status_code=404, detail="Query not found")

    return QueryResponse(**result)


@router.get("/{query_id}/claims")
async def get_query_claims(
    query_id: UUID, request: Request
) -> list[ClaimResponse]:
    """Get per-claim confidence breakdown for a query."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    claims = await _confidence.get_claim_breakdown(pool, tenant_id, query_id)
    return [ClaimResponse(**c) for c in claims]
