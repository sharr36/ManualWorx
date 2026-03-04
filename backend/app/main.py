"""ManualWorx API — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # --- Startup ---
    print("Starting ManualWorx API...")

    # Database
    app.state.db_pool = await create_pool()
    print("  Database pool created")

    # Run migrations
    await run_migrations(app.state.db_pool)
    print("  Migrations applied")

    # Redis (optional — graceful degradation)
    app.state.redis = None
    try:
        import redis.asyncio as aioredis

        app.state.redis = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
        await app.state.redis.ping()
        print("  Redis connected")
    except Exception as e:
        print(f"  Redis not available: {e}")

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
            print(f"  Qdrant collection '{settings.COLLECTION_NAME}' created")
        print("  Qdrant connected")
    except Exception as e:
        print(f"  Qdrant not available: {e}")

    print("ManualWorx API ready.")
    yield

    # --- Shutdown ---
    print("Shutting down ManualWorx API...")
    if app.state.redis:
        await app.state.redis.aclose()
    if app.state.qdrant:
        await app.state.qdrant.close()
    await app.state.db_pool.close()
    print("ManualWorx API stopped.")


app = FastAPI(
    title="ManualWorx API",
    description="AI-powered manual intelligence platform for heavy equipment mechanics",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Middleware (order matters: last added runs first) ---

# Rate limiting (innermost — runs after auth sets tenant context)
app.add_middleware(RateLimitMiddleware)

# Authentication (extracts session, sets request.state)
app.add_middleware(AuthMiddleware)

# CORS (outermost — handles preflight before anything else)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
