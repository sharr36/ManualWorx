"""Rate limiting middleware — tracks query usage against plan limits."""

from datetime import datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Paths that consume query quota
METERED_PATHS = {
    "/api/query",
    "/api/teach/explain",
    "/api/teach/walkthrough",
    "/api/teach/quiz/generate",
    "/api/assist",
    "/api/analyze/diagram",
    "/api/analyze/text",
    "/api/analyze/aggregate",
    "/api/viewer/annotate",
    "/api/viewer/generate-schematic",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Only meter POST requests to AI-consuming endpoints
        if request.method != "POST":
            return await call_next(request)

        path = request.url.path
        if path not in METERED_PATHS:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return await call_next(request)

        # Check usage in Redis
        redis = getattr(request.app.state, "redis", None)
        if not redis:
            return await call_next(request)

        current_month = datetime.now().strftime("%Y-%m")
        key = f"usage:{tenant_id}:{current_month}:queries"

        try:
            current = await redis.get(key)
            current = int(current) if current else 0

            # Get tenant's query limit from DB (cached in request state by auth middleware)
            pool = request.app.state.db_pool
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT query_limit_monthly FROM tenants WHERE id = $1",
                    tenant_id,
                )
                limit = row["query_limit_monthly"] if row else 25

            if current >= limit:
                return Response(
                    content='{"detail":"Monthly query limit exceeded. Upgrade your plan for more queries."}',
                    status_code=429,
                    media_type="application/json",
                )

            # Increment usage (actual increment happens after successful response in the route)
        except Exception:
            # Don't block requests if Redis is down
            pass

        return await call_next(request)
