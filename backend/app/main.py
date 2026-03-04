"""ManualWorx API — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .config import settings
from .database import create_pool, run_migrations
from .middleware.auth import AuthMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .routers import (
    analyze,
    auth,
    billing,
    documents,
    health,
    manuals,
    query,
    teaching,
    tenants,
    users,
    viewer,
)
from .utils.logging import RequestIDMiddleware, setup_logging

setup_logging(level=getattr(settings, "LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # --- Startup ---
    logger.info("Starting ManualWorx API...")

    # Database
    app.state.db_pool = await create_pool()
    logger.info("Database pool created")

    # Run migrations
    await run_migrations(app.state.db_pool)
    logger.info("Migrations applied")

    # Redis (optional — graceful degradation)
    app.state.redis = None
    try:
        import redis.asyncio as aioredis

        app.state.redis = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
        await app.state.redis.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis not available: %s", e)

    # Qdrant (optional — graceful degradation)
    app.state.qdrant = None
    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, VectorParams

        app.state.qdrant = AsyncQdrantClient(url=settings.QDRANT_URL)
        collections = await app.state.qdrant.get_collections()
        existing = {c.name for c in collections.collections}
        if settings.COLLECTION_NAME not in existing:
            await app.state.qdrant.create_collection(
                collection_name=settings.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION, distance=Distance.COSINE
                ),
            )
            logger.info("Qdrant collection '%s' created", settings.COLLECTION_NAME)
        logger.info("Qdrant connected")
    except Exception as e:
        logger.warning("Qdrant not available: %s", e)

    logger.info("ManualWorx API ready")
    yield

    # --- Shutdown ---
    logger.info("Shutting down ManualWorx API...")
    if app.state.redis:
        await app.state.redis.aclose()
    if app.state.qdrant:
        await app.state.qdrant.close()
    await app.state.db_pool.close()
    logger.info("ManualWorx API stopped")


app = FastAPI(
    title="ManualWorx API",
    description="AI-powered manual intelligence platform for heavy equipment mechanics",
    version="0.9.0",
    lifespan=lifespan,
)

# --- Middleware (order matters: last added runs first) ---

# Rate limiting (innermost — runs after auth sets tenant context)
app.add_middleware(RateLimitMiddleware)

# Authentication (extracts session, sets request.state)
app.add_middleware(AuthMiddleware)

# Request ID tracking
app.add_middleware(RequestIDMiddleware)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS (outermost — handles preflight before anything else)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)

# --- Routers ---
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(users.router)
app.include_router(billing.router)
app.include_router(billing.webhook_router)
app.include_router(manuals.router)
app.include_router(query.router)
app.include_router(documents.router)
app.include_router(teaching.router)
app.include_router(viewer.router)
app.include_router(analyze.router)
