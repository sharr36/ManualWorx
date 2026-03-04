"""Document generation endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..models.document import DocGenerateRequest, DocResponse
from ..services.document_service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["documents"])
_service = DocumentService()


@router.post("/generate")
async def generate_document(body: DocGenerateRequest, request: Request) -> DocResponse:
    """Generate a document from a query response."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        result = await _service.generate_document(
            pool=pool,
            tenant_id=tenant_id,
            query_id=body.query_id,
            doc_type=body.doc_type,
            doc_format=body.format,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return DocResponse(**result)


@router.get("")
async def list_documents(
    request: Request,
    doc_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[DocResponse]:
    """List generated documents for the current tenant."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    results = await _service.list_documents(
        pool, tenant_id, doc_type=doc_type, limit=limit, offset=offset
    )
    return [DocResponse(**r) for r in results]


@router.get("/{document_id}")
async def get_document(document_id: UUID, request: Request) -> DocResponse:
    """Get document metadata."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    result = await _service.get_document(pool, tenant_id, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocResponse(**result)


@router.get("/{document_id}/download")
async def download_document(document_id: UUID, request: Request):
    """Download a generated document via pre-signed URL redirect."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    url = await _service.get_download_url(pool, tenant_id, document_id)
    if not url:
        raise HTTPException(status_code=404, detail="Document not found")

    return RedirectResponse(url=url, status_code=302)


@router.delete("/{document_id}")
async def delete_document(document_id: UUID, request: Request) -> dict:
    """Delete a generated document."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    deleted = await _service.delete_document(pool, tenant_id, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"status": "deleted", "id": str(document_id)}
