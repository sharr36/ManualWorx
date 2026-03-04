"""Manual and page models."""

from pydantic import BaseModel

from manualworx_shared.constants import ManualType


class ManualUploadRequest(BaseModel):
    title: str
    make: str | None = None
    model: str | None = None
    manual_type: ManualType = ManualType.SERVICE


class ManualResponse(BaseModel):
    id: str
    title: str
    make: str | None = None
    model: str | None = None
    manual_type: str | None = None
    total_pages: int | None = None
    upload_status: str
    visibility: str | None = None
    created_at: str
    updated_at: str | None = None


class ManualDetailResponse(ManualResponse):
    pages_processed: int = 0
    original_pdf_url: str | None = None


class PageResponse(BaseModel):
    id: str
    manual_id: str
    page_number: int
    classification: str | None = None
    extracted_text: str | None = None
    image_url: str | None = None
    has_table: bool = False
    has_diagram: bool = False
