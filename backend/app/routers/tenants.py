"""Tenant management endpoints."""

from fastapi import APIRouter, HTTPException, Request

from ..models.tenant import TenantUpdateRequest
from ..routers.auth import _serialize_record
from ..services import tenant_service

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("/current")
async def get_current_tenant(request: Request) -> dict:
    """Get the current tenant."""
    pool = request.app.state.db_pool
    tenant = await tenant_service.get_tenant(pool, request.state.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _serialize_record(tenant)


@router.patch("/current")
async def update_current_tenant(request: Request, body: TenantUpdateRequest) -> dict:
    """Update the current tenant (owner only)."""
    if request.state.user_role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can update tenant settings")

    pool = request.app.state.db_pool
    tenant = await tenant_service.update_tenant(
        pool, request.state.tenant_id, name=body.name
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _serialize_record(tenant)
