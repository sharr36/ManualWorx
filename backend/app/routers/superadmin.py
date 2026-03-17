"""Super admin endpoints — system-wide visibility and management."""

import os
import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import settings

router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])


def _require_superadmin(request: Request) -> None:
    """Raise 403 if the current user is not a superadmin."""
    if not getattr(request.state, "is_superadmin", False):
        raise HTTPException(status_code=403, detail="Superadmin access required")


# ─── System Overview ─────────────────────────────────────────────────────────


@router.get("/overview")
async def system_overview(request: Request) -> dict:
    """System-wide stats across all tenants."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        tenants = await conn.fetchval("SELECT COUNT(*) FROM tenants")
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        manuals = await conn.fetchval("SELECT COUNT(*) FROM manuals")
        pages = await conn.fetchval("SELECT COUNT(*) FROM pages")
        chunks = await conn.fetchval("SELECT COUNT(*) FROM chunks")
        queries = await conn.fetchval("SELECT COUNT(*) FROM queries")
        documents = await conn.fetchval("SELECT COUNT(*) FROM documents")

        # Recent activity
        recent_manuals = await conn.fetchval(
            "SELECT COUNT(*) FROM manuals WHERE created_at > NOW() - INTERVAL '7 days'"
        )
        recent_queries = await conn.fetchval(
            "SELECT COUNT(*) FROM queries WHERE created_at > NOW() - INTERVAL '7 days'"
        )
        recent_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE last_login_at > NOW() - INTERVAL '7 days'"
        )

        # Processing status
        manuals_processing = await conn.fetchval(
            "SELECT COUNT(*) FROM manuals WHERE upload_status = 'processing'"
        )
        manuals_failed = await conn.fetchval(
            "SELECT COUNT(*) FROM manuals WHERE upload_status = 'failed'"
        )

    return {
        "totals": {
            "tenants": tenants,
            "users": users,
            "manuals": manuals,
            "pages": pages,
            "chunks": chunks,
            "queries": queries,
            "documents": documents,
        },
        "recent_7d": {
            "manuals": recent_manuals,
            "queries": recent_queries,
            "active_users": recent_users,
        },
        "processing": {
            "in_progress": manuals_processing,
            "failed": manuals_failed,
        },
    }


# ─── Tenant Management ───────────────────────────────────────────────────────


@router.get("/tenants")
async def list_tenants(request: Request) -> dict:
    """List all tenants with usage stats."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.id, t.name, t.slug, t.type, t.subscription_plan,
                   t.subscription_status, t.manual_limit, t.user_limit,
                   t.query_limit_monthly, t.created_at,
                   (SELECT COUNT(*) FROM users u WHERE u.tenant_id = t.id) AS user_count,
                   (SELECT COUNT(*) FROM manuals m WHERE m.tenant_id = t.id) AS manual_count,
                   (SELECT COUNT(*) FROM manuals m WHERE m.tenant_id = t.id AND m.upload_status = 'ready') AS ready_count,
                   (SELECT COUNT(*) FROM queries q WHERE q.tenant_id = t.id) AS query_count,
                   (SELECT u.email FROM users u WHERE u.id = t.owner_user_id) AS owner_email
            FROM tenants t
            ORDER BY t.created_at DESC
        """)

    tenants = []
    for r in rows:
        tenants.append({
            "id": str(r["id"]),
            "name": r["name"],
            "slug": r["slug"],
            "type": r["type"],
            "subscription_plan": r["subscription_plan"],
            "subscription_status": r["subscription_status"],
            "manual_limit": r["manual_limit"],
            "user_limit": r["user_limit"],
            "query_limit_monthly": r["query_limit_monthly"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "owner_email": r["owner_email"],
            "user_count": r["user_count"],
            "manual_count": r["manual_count"],
            "ready_count": r["ready_count"],
            "query_count": r["query_count"],
        })

    return {"tenants": tenants, "total": len(tenants)}


# ─── All Users ────────────────────────────────────────────────────────────────


@router.get("/users")
async def list_all_users(request: Request) -> dict:
    """List all users across all tenants."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.id, u.email, u.name, u.role, u.skill_level,
                   u.last_login_at, u.created_at,
                   t.name AS tenant_name, t.slug AS tenant_slug
            FROM users u
            JOIN tenants t ON t.id = u.tenant_id
            ORDER BY u.created_at DESC
        """)

    users = []
    for r in rows:
        users.append({
            "id": str(r["id"]),
            "email": r["email"],
            "name": r["name"],
            "role": r["role"],
            "skill_level": r["skill_level"],
            "last_login_at": r["last_login_at"].isoformat() if r["last_login_at"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "tenant_name": r["tenant_name"],
            "tenant_slug": r["tenant_slug"],
        })

    return {"users": users, "total": len(users)}


# ─── Migrations ───────────────────────────────────────────────────────────────


def _get_migrations_dir() -> Path:
    return Path(__file__).parent.parent.parent / "migrations"


@router.get("/migrations")
async def get_migrations(request: Request) -> dict:
    """Get applied and pending migration status with full SQL content."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    # Get applied migrations
    async with pool.acquire() as conn:
        applied_rows = await conn.fetch(
            "SELECT filename, applied_at FROM _migrations ORDER BY filename"
        )
    applied = {r["filename"]: r["applied_at"].isoformat() for r in applied_rows}

    # Get all migration files on disk
    migrations_dir = _get_migrations_dir()
    all_files = []
    if migrations_dir.exists():
        all_files = sorted(
            f for f in os.listdir(migrations_dir)
            if f.endswith(".sql")
        )

    migrations = []
    for filename in all_files:
        sql_path = migrations_dir / filename
        sql_content = sql_path.read_text()
        line_count = len(sql_content.strip().splitlines())

        migrations.append({
            "filename": filename,
            "applied": filename in applied,
            "applied_at": applied.get(filename),
            "line_count": line_count,
            "sql": sql_content,
        })

    pending = [m for m in migrations if not m["applied"]]

    return {
        "migrations": migrations,
        "total": len(migrations),
        "applied": len(applied),
        "pending": len(pending),
    }


@router.post("/migrations/run")
async def run_pending_migrations(request: Request) -> dict:
    """Run all pending migrations in order."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    migrations_dir = _get_migrations_dir()
    if not migrations_dir.exists():
        return {"applied": [], "errors": []}

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT filename FROM _migrations")
        applied = {r["filename"] for r in rows}

        all_files = sorted(
            f for f in os.listdir(migrations_dir)
            if f.endswith(".sql")
        )

        results = []
        errors = []

        for filename in all_files:
            if filename in applied:
                continue

            sql = (migrations_dir / filename).read_text()
            try:
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO _migrations (filename) VALUES ($1)", filename
                )
                results.append({"filename": filename, "status": "applied"})
            except Exception as e:
                errors.append({"filename": filename, "error": str(e)})
                break  # Stop on first failure

    return {"applied": results, "errors": errors}


@router.post("/migrations/apply/{filename}")
async def apply_single_migration(filename: str, request: Request) -> dict:
    """Apply a single pending migration by filename."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    # Validate filename (prevent path traversal)
    if not re.match(r"^[\w\-]+\.sql$", filename):
        raise HTTPException(status_code=400, detail="Invalid migration filename")

    migrations_dir = _get_migrations_dir()
    sql_path = migrations_dir / filename
    if not sql_path.exists():
        raise HTTPException(status_code=404, detail=f"Migration file not found: {filename}")

    async with pool.acquire() as conn:
        # Check if already applied
        row = await conn.fetchrow(
            "SELECT filename FROM _migrations WHERE filename = $1", filename
        )
        if row:
            raise HTTPException(
                status_code=409,
                detail=f"Migration {filename} is already applied. Use repair to re-run.",
            )

        sql = sql_path.read_text()
        try:
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO _migrations (filename) VALUES ($1)", filename
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Migration failed: {e}")

    return {"status": "applied", "filename": filename}


@router.post("/migrations/repair/{filename}")
async def repair_migration(filename: str, request: Request) -> dict:
    """Re-run an already-applied migration (repair mode).

    Removes the migration record, re-executes the SQL, then re-records it.
    Useful for fixing schema issues or re-applying migrations that use
    IF NOT EXISTS / CREATE OR REPLACE patterns.
    """
    _require_superadmin(request)
    pool = request.app.state.db_pool

    if not re.match(r"^[\w\-]+\.sql$", filename):
        raise HTTPException(status_code=400, detail="Invalid migration filename")

    migrations_dir = _get_migrations_dir()
    sql_path = migrations_dir / filename
    if not sql_path.exists():
        raise HTTPException(status_code=404, detail=f"Migration file not found: {filename}")

    sql = sql_path.read_text()

    async with pool.acquire() as conn:
        try:
            # Remove old tracking record
            await conn.execute(
                "DELETE FROM _migrations WHERE filename = $1", filename
            )
            # Re-execute the migration
            await conn.execute(sql)
            # Re-record with fresh timestamp
            await conn.execute(
                "INSERT INTO _migrations (filename) VALUES ($1)", filename
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Repair failed: {e}")

    return {"status": "repaired", "filename": filename}


class RepairSQLRequest(BaseModel):
    sql: str
    description: str = ""


@router.post("/migrations/execute-sql")
async def execute_repair_sql(body: RepairSQLRequest, request: Request) -> dict:
    """Execute ad-hoc repair SQL. Use for emergency fixes only.

    Only allows DDL and safe DML — blocks DROP DATABASE, TRUNCATE on
    system tables, and other destructive operations.
    """
    _require_superadmin(request)
    pool = request.app.state.db_pool

    sql = body.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL cannot be empty")

    # Block obviously dangerous statements
    sql_upper = sql.upper()
    blocked = [
        "DROP DATABASE", "DROP SCHEMA", "TRUNCATE _migrations",
        "DELETE FROM _migrations", "DROP TABLE _migrations",
    ]
    for pattern in blocked:
        if pattern in sql_upper:
            raise HTTPException(
                status_code=400,
                detail=f"Blocked: '{pattern}' is not allowed via repair SQL",
            )

    async with pool.acquire() as conn:
        try:
            result = await conn.execute(sql)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"SQL execution failed: {e}")

    return {
        "status": "executed",
        "result": result,
        "description": body.description,
    }


# ─── System Health ────────────────────────────────────────────────────────────


@router.get("/health")
async def system_health(request: Request) -> dict:
    """Check health of all system components."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    checks = {}

    # PostgreSQL
    try:
        async with pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            db_size = await conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )
            active_connections = await conn.fetchval(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
        checks["postgres"] = {
            "status": "healthy",
            "version": version,
            "database_size": db_size,
            "active_connections": active_connections,
        }
    except Exception as e:
        checks["postgres"] = {"status": "unhealthy", "error": str(e)}

    # Redis
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        try:
            info = await redis_client.info("server")
            checks["redis"] = {
                "status": "healthy",
                "version": info.get("redis_version", "unknown"),
            }
        except Exception as e:
            checks["redis"] = {"status": "unhealthy", "error": str(e)}
    else:
        checks["redis"] = {"status": "not_configured"}

    # Qdrant
    qdrant = getattr(request.app.state, "qdrant", None)
    if qdrant:
        try:
            collections = await qdrant.get_collections()
            collection_names = [c.name for c in collections.collections]
            checks["qdrant"] = {
                "status": "healthy",
                "collections": collection_names,
            }
        except Exception as e:
            checks["qdrant"] = {"status": "unhealthy", "error": str(e)}
    else:
        checks["qdrant"] = {"status": "not_configured"}

    # S3/Tigris
    s3 = getattr(request.app.state, "s3", None)
    if s3:
        try:
            s3.head_bucket(Bucket=settings.BUCKET_NAME)
            checks["storage"] = {
                "status": "healthy",
                "bucket": settings.BUCKET_NAME,
            }
        except Exception as e:
            checks["storage"] = {"status": "unhealthy", "error": str(e)}
    else:
        checks["storage"] = {"status": "not_configured"}

    # Config summary (non-sensitive)
    checks["config"] = {
        "ocr_provider": settings.OCR_PROVIDER,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "default_model": settings.DEFAULT_MODEL,
        "rerank_enabled": settings.RERANK_ENABLED,
        "has_anthropic_key": bool(settings.ANTHROPIC_API_KEY),
        "has_together_key": bool(settings.TOGETHER_API_KEY),
        "has_stripe_key": bool(settings.STRIPE_SECRET_KEY),
    }

    overall = all(
        c.get("status") in ("healthy", "not_configured")
        for key, c in checks.items()
        if key != "config"
    )

    return {"healthy": overall, "checks": checks}


# ─── Worker Queue ─────────────────────────────────────────────────────────────


@router.get("/worker-queue")
async def worker_queue_status(request: Request) -> dict:
    """Get arq worker queue status from Redis."""
    _require_superadmin(request)

    redis_client = getattr(request.app.state, "redis", None)
    if not redis_client:
        return {"status": "redis_not_configured", "jobs": []}

    try:
        # arq stores job results with prefix "arq:result:"
        # and queued jobs in "arq:queue"
        queue_len = await redis_client.llen("arq:queue")

        # Get recent job results
        result_keys = []
        async for key in redis_client.scan_iter("arq:result:*", count=100):
            result_keys.append(key)

        return {
            "status": "connected",
            "queue_length": queue_len,
            "result_count": len(result_keys),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─── Manual Management (cross-tenant) ────────────────────────────────────────


@router.get("/manuals")
async def list_all_manuals(request: Request) -> dict:
    """List all manuals across all tenants."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.id, m.title, m.make, m.model, m.manual_type,
                   m.total_pages, m.upload_status, m.created_at,
                   t.name AS tenant_name, t.slug AS tenant_slug,
                   (SELECT COUNT(*) FROM pages p WHERE p.manual_id = m.id) AS page_count,
                   (SELECT COUNT(*) FROM chunks c
                    JOIN pages p ON p.id = c.page_id
                    WHERE p.manual_id = m.id) AS chunk_count,
                   (SELECT COUNT(*) FROM diagram_annotations da
                    JOIN pages p ON p.id = da.page_id
                    WHERE p.manual_id = m.id) AS annotation_count
            FROM manuals m
            JOIN tenants t ON t.id = m.tenant_id
            ORDER BY m.created_at DESC
            LIMIT 200
        """)

    manuals = []
    for r in rows:
        manuals.append({
            "id": str(r["id"]),
            "title": r["title"],
            "make": r["make"],
            "model": r["model"],
            "manual_type": r["manual_type"],
            "total_pages": r["total_pages"],
            "upload_status": r["upload_status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "tenant_name": r["tenant_name"],
            "tenant_slug": r["tenant_slug"],
            "page_count": r["page_count"],
            "chunk_count": r["chunk_count"],
            "annotation_count": r["annotation_count"],
        })

    return {"manuals": manuals, "total": len(manuals)}


@router.post("/manuals/{manual_id}/reprocess")
async def reprocess_manual(manual_id: UUID, request: Request) -> dict:
    """Re-trigger ingestion for a manual (cross-tenant)."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, tenant_id, upload_status FROM manuals WHERE id = $1",
            manual_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Manual not found")

    # Enqueue re-ingestion
    redis_client = getattr(request.app.state, "redis", None)
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not available for job queue")

    try:
        from arq.connections import ArqRedis, create_pool as create_arq_pool
        from manualworx_shared.config import arq_redis_settings
        arq: ArqRedis = await create_arq_pool(arq_redis_settings(settings.REDIS_URL))
        await arq.enqueue_job("ingest_manual", str(manual_id), str(row["tenant_id"]))
        await arq.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {e}")

    # Reset status
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE manuals SET upload_status = 'processing', updated_at = NOW() WHERE id = $1",
            manual_id,
        )

    return {"status": "reprocessing", "manual_id": str(manual_id)}


@router.post("/manuals/{manual_id}/re-embed")
async def re_embed_manual(manual_id: UUID, request: Request) -> dict:
    """Re-embed all chunks for a manual (when Qdrant was unavailable during ingestion)."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, tenant_id FROM manuals WHERE id = $1", manual_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Manual not found")

    # Get all chunk IDs for this manual
    async with pool.acquire() as conn:
        chunk_rows = await conn.fetch(
            """SELECT c.id FROM chunks c
               JOIN pages p ON p.id = c.page_id
               WHERE p.manual_id = $1""",
            manual_id,
        )

    if not chunk_rows:
        return {"status": "no_chunks", "manual_id": str(manual_id)}

    chunk_ids = [str(r["id"]) for r in chunk_rows]

    # Enqueue embedding job in batches of 100
    try:
        from arq.connections import ArqRedis, create_pool as create_arq_pool
        from manualworx_shared.config import arq_redis_settings
        arq: ArqRedis = await create_arq_pool(arq_redis_settings(settings.REDIS_URL))

        batch_size = 100
        jobs_enqueued = 0
        for i in range(0, len(chunk_ids), batch_size):
            batch = chunk_ids[i:i + batch_size]
            await arq.enqueue_job("generate_embeddings", batch)
            jobs_enqueued += 1

        await arq.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue embedding: {e}")

    return {
        "status": "embedding_queued",
        "manual_id": str(manual_id),
        "chunks": len(chunk_ids),
        "jobs": jobs_enqueued,
    }


@router.post("/manuals/{manual_id}/reclassify")
async def reclassify_manual(manual_id: UUID, request: Request) -> dict:
    """Re-run AI classification on all pages of a manual (cross-tenant)."""
    _require_superadmin(request)
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, tenant_id FROM manuals WHERE id = $1", manual_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Manual not found")

    async with pool.acquire() as conn:
        page_rows = await conn.fetch(
            "SELECT id FROM pages WHERE manual_id = $1", manual_id,
        )

    if not page_rows:
        return {"status": "no_pages"}

    page_ids = [str(r["id"]) for r in page_rows]

    try:
        from arq.connections import ArqRedis, create_pool as create_arq_pool
        from manualworx_shared.config import arq_redis_settings
        arq: ArqRedis = await create_arq_pool(arq_redis_settings(settings.REDIS_URL))
        await arq.enqueue_job("classify_pages", str(manual_id), page_ids)
        await arq.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue classification: {e}")

    return {"status": "classification_queued", "pages": len(page_ids)}
