"""Admin analytics endpoints — owner-only usage statistics."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from manualworx_shared.constants import UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def get_tenant_stats(request: Request) -> dict:
    """Return usage statistics for the current tenant. Owner-only."""
    role = getattr(request.state, "user_role", None)
    if role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Only the owner can view analytics")

    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        # Total manuals
        total_manuals = await conn.fetchval(
            "SELECT COUNT(*) FROM manuals WHERE tenant_id = $1",
            tenant_id,
        )

        # Total pages ingested
        total_pages = await conn.fetchval(
            """
            SELECT COUNT(*) FROM pages p
            JOIN manuals m ON p.manual_id = m.id
            WHERE m.tenant_id = $1
            """,
            tenant_id,
        )

        # Queries last 30 days
        queries_30d = await conn.fetchval(
            """
            SELECT COUNT(*) FROM queries
            WHERE tenant_id = $1 AND created_at >= $2 - INTERVAL '30 days'
            """,
            tenant_id,
            now,
        )

        # Documents generated
        total_documents = await conn.fetchval(
            """
            SELECT COUNT(*) FROM documents
            WHERE tenant_id = $1
            """,
            tenant_id,
        )

        # Active users (last 7 days)
        active_users = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT user_id) FROM sessions
            WHERE expires_at > $1
            AND user_id IN (SELECT id FROM users WHERE tenant_id = $2)
            """,
            now,
            tenant_id,
        )

        # Total team members
        total_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE tenant_id = $1",
            tenant_id,
        )

    return {
        "total_manuals": total_manuals or 0,
        "total_pages": total_pages or 0,
        "queries_30d": queries_30d or 0,
        "total_documents": total_documents or 0,
        "active_users_7d": active_users or 0,
        "total_users": total_users or 0,
    }
