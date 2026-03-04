"""Health check endpoint."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/api/livez")
async def liveness() -> dict:
    """Lightweight liveness probe — no backing-service checks."""
    return {"status": "ok"}


@router.get("/api/health")
async def health_check(request: Request) -> dict:
    """Check connectivity to all backing services."""
    checks = {}

    # Database
    try:
        pool = request.app.state.db_pool
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis
    try:
        redis = request.app.state.redis
        if redis:
            await redis.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not configured"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Qdrant
    try:
        qdrant = request.app.state.qdrant
        if qdrant:
            await qdrant.get_collections()
            checks["qdrant"] = "ok"
        else:
            checks["qdrant"] = "not configured"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values() if v != "not configured")
    return {
        "status": "healthy" if all_ok else "degraded",
        "services": checks,
    }
