"""Authentication service — signup, login, logout, session validation."""

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg

from ..utils.security import generate_session_token, hash_password, hash_token, verify_password

SESSION_DURATION_DAYS = 30


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug[:50]


async def signup(
    pool: asyncpg.Pool,
    name: str,
    email: str,
    password: str,
    tenant_name: str,
    tenant_type: str,
) -> dict:
    """Create a new tenant, user (owner), and session."""
    password_hashed = hash_password(password)
    token = generate_session_token()
    token_hashed = hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)
    slug = _slugify(tenant_name)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Create tenant
            tenant = await conn.fetchrow(
                """
                INSERT INTO tenants (type, name, slug)
                VALUES ($1, $2, $3)
                RETURNING id, type, name, slug, subscription_plan, subscription_status,
                          manual_limit, user_limit, query_limit_monthly,
                          created_at, updated_at
                """,
                tenant_type, tenant_name, slug,
            )

            # Create user (owner)
            user = await conn.fetchrow(
                """
                INSERT INTO users (tenant_id, email, name, password_hash, role)
                VALUES ($1, $2, $3, $4, 'owner')
                RETURNING id, tenant_id, email, name, role, skill_level,
                          created_at, updated_at
                """,
                tenant["id"], email, name, password_hashed,
            )

            # Set owner on tenant
            await conn.execute(
                "UPDATE tenants SET owner_user_id = $1 WHERE id = $2",
                user["id"], tenant["id"],
            )

            # Create session
            await conn.execute(
                """
                INSERT INTO sessions (user_id, token_hash, expires_at)
                VALUES ($1, $2, $3)
                """,
                user["id"], token_hashed, expires_at,
            )

    return {
        "token": token,
        "user": dict(user),
        "tenant": dict(tenant),
    }


async def login(pool: asyncpg.Pool, email: str, password: str) -> dict | None:
    """Validate credentials and create a new session."""
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT u.id, u.tenant_id, u.email, u.name, u.role, u.skill_level,
                   u.password_hash, u.created_at, u.updated_at
            FROM users u
            WHERE u.email = $1
            """,
            email,
        )

    if not user or not verify_password(password, user["password_hash"]):
        return None

    token = generate_session_token()
    token_hashed = hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS)

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES ($1, $2, $3)",
            user["id"], token_hashed, expires_at,
        )

        # Update last login
        await conn.execute(
            "UPDATE users SET last_login_at = NOW() WHERE id = $1",
            user["id"],
        )

        # Get tenant info
        tenant = await conn.fetchrow(
            """
            SELECT id, type, name, slug, subscription_plan, subscription_status,
                   manual_limit, user_limit, query_limit_monthly,
                   created_at, updated_at
            FROM tenants WHERE id = $1
            """,
            user["tenant_id"],
        )

    user_dict = dict(user)
    del user_dict["password_hash"]

    return {
        "token": token,
        "user": user_dict,
        "tenant": dict(tenant),
    }


async def logout(pool: asyncpg.Pool, token: str) -> None:
    """Delete a session."""
    token_hashed = hash_token(token)
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM sessions WHERE token_hash = $1",
            token_hashed,
        )


async def get_current_user(pool: asyncpg.Pool, user_id: UUID, tenant_id: UUID) -> dict | None:
    """Get the current user and tenant info."""
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, tenant_id, email, name, role, skill_level,
                   created_at, updated_at, last_login_at
            FROM users WHERE id = $1
            """,
            user_id,
        )
        tenant = await conn.fetchrow(
            """
            SELECT id, type, name, slug, subscription_plan, subscription_status,
                   manual_limit, user_limit, query_limit_monthly,
                   created_at, updated_at
            FROM tenants WHERE id = $1
            """,
            tenant_id,
        )

    if not user or not tenant:
        return None

    return {
        "user": dict(user),
        "tenant": dict(tenant),
    }
