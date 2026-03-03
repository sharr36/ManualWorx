"""Manual management endpoints (Phase 1)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..models.manual import ManualUploadRequest

router = APIRouter(prefix="/api/manuals", tags=["manuals"])


@router.post("/upload")
async def upload_manual(body: ManualUploadRequest) -> dict:
    """Upload a new manual for processing."""
    raise HTTPException(status_code=501, detail="Manual upload coming in Phase 1")


@router.get("")
async def list_manuals() -> list[dict]:
    """List all manuals for the current tenant."""
    raise HTTPException(status_code=501, detail="Manual listing coming in Phase 1")


@router.get("/{manual_id}")
async def get_manual(manual_id: UUID) -> dict:
    """Get manual details and processing status."""
    raise HTTPException(status_code=501, detail="Manual details coming in Phase 1")


@router.delete("/{manual_id}")
async def delete_manual(manual_id: UUID) -> dict:
    """Delete a manual."""
    raise HTTPException(status_code=501, detail="Manual deletion coming in Phase 1")
