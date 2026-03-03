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
    make: str | None
    model: str | None
    manual_type: str
    total_pages: int | None
    upload_status: str
    created_at: str
