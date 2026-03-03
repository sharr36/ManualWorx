"""Tenant request/response models."""

from pydantic import BaseModel


class TenantUpdateRequest(BaseModel):
    name: str | None = None
