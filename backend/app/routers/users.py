"""User management endpoints (tenant-scoped)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from ..models.user import UserInviteRequest, UserUpdateRequest
from ..routers.auth import _serialize_record
from ..services import tenant_service
from ..utils.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
async def list_users(request: Request) -> list[dict]:
    """List all users in the current tenant."""
    pool = request.app.state.db_pool
    users = await tenant_service.get_users(pool, request.state.tenant_id)
    return [_serialize_record(u) for u in users]


@router.post("")
async def invite_user(request: Request, body: UserInviteRequest) -> dict:
    """Invite a new user to the tenant (owner only)."""
    if request.state.user_role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can invite users")

    pool = request.app.state.db_pool

    # Generate a temporary password hash (the invited user will reset on first login)
    temp_password_hash = hash_password("changeme-" + body.email)

    try:
        user = await tenant_service.invite_user(
            pool,
            tenant_id=request.state.tenant_id,
            email=body.email,
            name=body.name,
            role=body.role,
            temp_password_hash=temp_password_hash,
        )
    except Exception as e:
        error_msg = str(e)
        if "unique" in error_msg.lower() and "email" in error_msg.lower():
            raise HTTPException(status_code=409, detail="Email already registered")
        raise HTTPException(status_code=400, detail="Failed to invite user")

    return _serialize_record(user)


@router.get("/{user_id}")
async def get_user(request: Request, user_id: UUID) -> dict:
    """Get a specific user by ID."""
    pool = request.app.state.db_pool
    users = await tenant_service.get_users(pool, request.state.tenant_id)
    for u in users:
        if u["id"] == user_id:
            return _serialize_record(u)
    raise HTTPException(status_code=404, detail="User not found")


@router.patch("/{user_id}")
async def update_user(request: Request, user_id: UUID, body: UserUpdateRequest) -> dict:
    """Update a user (owner only)."""
    if request.state.user_role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can update users")

    pool = request.app.state.db_pool
    user = await tenant_service.update_user(
        pool, user_id, name=body.name, role=body.role, skill_level=body.skill_level
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found or no changes")
    return _serialize_record(user)


@router.delete("/{user_id}")
async def delete_user(request: Request, user_id: UUID) -> dict:
    """Remove a user from the tenant (owner only)."""
    if request.state.user_role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can remove users")

    if user_id == request.state.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    pool = request.app.state.db_pool
    deleted = await tenant_service.delete_user(pool, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok"}
