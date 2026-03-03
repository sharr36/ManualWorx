"""Document generation models."""

from pydantic import BaseModel

from manualworx_shared.constants import DocumentFormat, DocumentType


class DocGenerateRequest(BaseModel):
    query_id: str
    doc_type: DocumentType
    format: DocumentFormat = DocumentFormat.PDF


class DocResponse(BaseModel):
    id: str
    doc_type: str
    format: str
    file_url: str | None
    created_at: str
