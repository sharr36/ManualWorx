"""Tenant management service."""

from uuid import UUID

import asyncpg

from ..database import set_tenant_context


async def get_tenant(pool: asyncpg.Pool, tenant_id: UUID) -> dict | None:
    """Get tenant details."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, type, name, slug, subscription_plan, subscription_status,
                   manual_limit, user_limit, query_limit_monthly,
                   created_at, updated_at
            FROM tenants WHERE id = $1
            """,
            tenant_id,
        )
    return dict(row) if row else None


async def update_tenant(pool: asyncpg.Pool, tenant_id: UUID, name: str | None) -> dict | None:
    """Update tenant details."""
    updates = []
    params = []
    param_idx = 1

    if name is not None:
        updates.append(f"name = ${param_idx}")
        params.append(name)
        param_idx += 1

    if not updates:
        return await get_tenant(pool, tenant_id)

    updates.append(f"updated_at = NOW()")
    params.append(tenant_id)

    query = f"""
        UPDATE tenants SET {', '.join(updates)}
        WHERE id = ${param_idx}
        RETURNING id, type, name, slug, subscription_plan, subscription_status,
                  manual_limit, user_limit, query_limit_monthly,
                  created_at, updated_at
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
    return dict(row) if row else None


async def get_users(pool: asyncpg.Pool, tenant_id: UUID) -> list[dict]:
    """Get all users for a tenant."""
    async with pool.acquire() as conn:
        await set_tenant_context(conn, tenant_id)
        rows = await conn.fetch(
            """
            SELECT id, tenant_id, email, name, role, skill_level,
                   last_login_at, created_at, updated_at
            FROM users
            ORDER BY created_at
            """
        )
    return [dict(row) for row in rows]


async def invite_user(
    pool: asyncpg.Pool,
    tenant_id: UUID,
    email: str,
    name: str,
    role: str,
    temp_password_hash: str,
) -> dict:
    """Invite a new user to a tenant."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (tenant_id, email, name, password_hash, role)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, tenant_id, email, name, role, skill_level,
                      created_at, updated_at
            """,
            tenant_id, email, name, temp_password_hash, role,
        )
    return dict(row)


async def update_user(
    pool: asyncpg.Pool, user_id: UUID, **kwargs
) -> dict | None:
    """Update a user's details."""
    updates = []
    params = []
    param_idx = 1

    for field in ("name", "role", "skill_level"):
        if field in kwargs and kwargs[field] is not None:
            updates.append(f"{field} = ${param_idx}")
            params.append(kwargs[field])
            param_idx += 1

    if not updates:
        return None

    updates.append("updated_at = NOW()")
    params.append(user_id)

    query = f"""
        UPDATE users SET {', '.join(updates)}
        WHERE id = ${param_idx}
        RETURNING id, tenant_id, email, name, role, skill_level,
                  created_at, updated_at
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
    return dict(row) if row else None


async def delete_user(pool: asyncpg.Pool, user_id: UUID) -> bool:
    """Delete a user."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM users WHERE id = $1", user_id
        )
    return result == "DELETE 1"
