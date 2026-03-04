"""Rate limiting middleware — tracks query usage against plan limits."""

import logging
from datetime import datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from manualworx_shared.constants import RATE_LIMIT_CACHE_TTL

logger = logging.getLogger(__name__)

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
        usage_key = f"usage:{tenant_id}:{current_month}:queries"
        limit_key = f"limit:{tenant_id}:queries"

        try:
            current = await redis.get(usage_key)
            current = int(current) if current else 0

            # Check cached tenant limit first (avoids DB hit on every request)
            limit = await redis.get(limit_key)
            if limit is not None:
                limit = int(limit)
            else:
                # Cache miss — fetch from DB and cache
                pool = request.app.state.db_pool
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT query_limit_monthly FROM tenants WHERE id = $1",
                        tenant_id,
                    )
                    limit = row["query_limit_monthly"] if row else 25
                await redis.set(limit_key, limit, ex=RATE_LIMIT_CACHE_TTL)

            if current >= limit:
                logger.info(
                    "Rate limit hit: tenant=%s usage=%d/%d path=%s",
                    tenant_id, current, limit, path,
                )
                return Response(
                    content='{"detail":"Monthly query limit exceeded. Upgrade your plan for more queries."}',
                    status_code=429,
                    media_type="application/json",
                )

        except Exception as e:
            # Don't block requests if Redis is down
            logger.warning("Rate limit check failed: %s", e)

        return await call_next(request)
