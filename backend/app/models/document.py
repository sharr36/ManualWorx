"""Document generation models."""

from pydantic import BaseModel

from manualworx_shared.constants import DocumentFormat, DocumentType


class DocGenerateRequest(BaseModel):
    query_id: str
    doc_type: DocumentType
    format: DocumentFormat = DocumentFormat.PDF


class DocResponse(BaseModel):
    id: str
    query_id: str | None = None
    doc_type: str
    format: str
    file_url: str | None = None
    query_text: str | None = None
    latency_ms: int | None = None
    created_at: str | None = None
