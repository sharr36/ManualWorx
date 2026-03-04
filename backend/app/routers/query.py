"""Query and chat endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from ..models.query import (
    FollowupRequest,
    QueryListItem,
    QueryRequest,
    QueryResponse,
)
from ..services.query_service import QueryService

router = APIRouter(prefix="/api/query", tags=["query"])
_service = QueryService()


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
