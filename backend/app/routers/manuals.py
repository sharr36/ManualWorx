"""Manual management endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form

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
