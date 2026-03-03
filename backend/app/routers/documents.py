"""Document generation endpoints (Phase 4)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..models.document import DocGenerateRequest

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/generate")
async def generate_document(body: DocGenerateRequest) -> dict:
    """Generate a document from a query response."""
    raise HTTPException(status_code=501, detail="Document generation coming in Phase 4")


@router.get("/{document_id}/download")
async def download_document(document_id: UUID) -> dict:
    """Download a generated document."""
    raise HTTPException(status_code=501, detail="Document download coming in Phase 4")
