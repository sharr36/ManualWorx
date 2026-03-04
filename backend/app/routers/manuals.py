"""Manual management endpoints."""

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse, StreamingResponse

from ..models.manual import ManualDetailResponse, ManualResponse, PageResponse
from ..services.manual_service import ManualService
from manualworx_shared.constants import ManualType, UserRole

router = APIRouter(prefix="/api/manuals", tags=["manuals"])
_service = ManualService()


@router.post("/upload")
async def upload_manual(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    make: str = Form(None),
    model: str = Form(None),
    manual_type: str = Form("service"),
) -> ManualResponse:
    """Upload a new manual PDF for processing."""
    # Validate PDF
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # RBAC: owner or manager can upload
    role = getattr(request.state, "user_role", None)
    if role not in (UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only owners and managers can upload manuals")

    tenant_id = request.state.tenant_id
    pool = request.app.state.db_pool
    redis = getattr(request.app.state, "redis", None)

    pdf_bytes = await file.read()

    try:
        result = await _service.upload_manual(
            pool=pool,
            redis=redis,
            tenant_id=tenant_id,
            title=title,
            make=make,
            model=model,
            manual_type=manual_type,
            pdf_bytes=pdf_bytes,
            filename=file.filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ManualResponse(**result)


@router.get("")
async def list_manuals(request: Request) -> list[ManualResponse]:
    """List all manuals for the current tenant."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    results = await _service.list_manuals(pool, tenant_id)
    return [ManualResponse(**r) for r in results]


@router.get("/{manual_id}")
async def get_manual(manual_id: UUID, request: Request) -> ManualDetailResponse:
    """Get manual details and processing status."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    result = await _service.get_manual(pool, tenant_id, manual_id)
    if not result:
        raise HTTPException(status_code=404, detail="Manual not found")

    return ManualDetailResponse(**result)


@router.get("/{manual_id}/pages")
async def get_manual_pages(manual_id: UUID, request: Request) -> list[PageResponse]:
    """Get all pages for a manual."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    pages = await _service.get_manual_pages(pool, tenant_id, manual_id)
    return [
        PageResponse(
            id=str(p["id"]),
            manual_id=str(p["manual_id"]),
            page_number=p["page_number"],
            classification=p["classification"],
            extracted_text=p["extracted_text"],
            image_url=p["image_url"],
            has_table=p["has_table"],
            has_diagram=p["has_diagram"],
        )
        for p in pages
    ]


@router.get("/{manual_id}/progress")
async def manual_progress(manual_id: UUID, request: Request):
    """Stream ingestion progress via SSE.

    Subscribes to Redis pub/sub channel `progress:{manual_id}` and streams
    events until the manual reaches 'ready' or 'failed' status.
    """
    redis = getattr(request.app.state, "redis", None)
    if not redis:
        raise HTTPException(status_code=503, detail="Progress tracking unavailable")

    async def event_generator():
        pubsub = redis.pubsub()
        channel = f"progress:{manual_id}"
        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg and msg["type"] == "message":
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"

                    # Close stream when done
                    try:
                        parsed = json.loads(data)
                        if parsed.get("stage") in ("ready", "failed"):
                            break
                    except Exception:
                        pass
                else:
                    # Send keepalive to prevent connection timeout
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{manual_id}/pages/{page_number}/image")
async def get_page_image(manual_id: UUID, page_number: int, request: Request):
    """Proxy page images via pre-signed URL redirect.

    Generates a pre-signed Tigris URL and redirects the client, avoiding
    exposure of S3 credentials.
    """
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    # Verify the page exists and belongs to the tenant
    async with pool.acquire() as conn:
        page = await conn.fetchrow(
            """
            SELECT p.image_url
            FROM pages p
            JOIN manuals m ON p.manual_id = m.id
            WHERE p.manual_id = $1 AND p.page_number = $2 AND m.tenant_id = $3
            """,
            manual_id,
            page_number,
            tenant_id,
        )

    if not page or not page["image_url"]:
        raise HTTPException(status_code=404, detail="Page image not found")

    # Generate pre-signed URL from storage provider
    from ..providers import get_storage_provider
    storage = get_storage_provider()
    url = await storage.get_url(page["image_url"])

    return RedirectResponse(url=url, status_code=302)


@router.delete("/{manual_id}")
async def delete_manual(manual_id: UUID, request: Request) -> dict:
    """Delete a manual."""
    # RBAC: owner or manager can delete
    role = getattr(request.state, "user_role", None)
    if role not in (UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only owners and managers can delete manuals")

    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    deleted = await _service.delete_manual(pool, tenant_id, manual_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Manual not found")

    return {"status": "deleted", "id": str(manual_id)}
