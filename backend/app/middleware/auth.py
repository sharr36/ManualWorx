"""Authentication middleware — validates session tokens on every request."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ..database import set_tenant_context
from ..utils.security import hash_token

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/api/health",
    "/api/auth/signup",
    "/api/auth/login",
    "/api/webhooks/stripe",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip auth for public paths
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Extract session token from cookie or Authorization header
        token = None
        cookie_token = request.cookies.get("manualworx_session")
        if cookie_token:
            token = cookie_token
        else:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return Response(
                content='{"detail":"Not authenticated"}',
                status_code=401,
                media_type="application/json",
            )

        # Validate the session
        token_hash = hash_token(token)
        pool = request.app.state.db_pool

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT s.user_id, s.expires_at,
                       u.tenant_id, u.role, u.name, u.email, u.skill_level
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token_hash = $1
                """,
                token_hash,
            )

        if not row:
            return Response(
                content='{"detail":"Invalid session"}',
                status_code=401,
                media_type="application/json",
            )

        if row["expires_at"] < datetime.now(timezone.utc):
            return Response(
                content='{"detail":"Session expired"}',
                status_code=401,
                media_type="application/json",
            )

        # Set user and tenant info on the request state
        request.state.user_id = row["user_id"]
        request.state.tenant_id = row["tenant_id"]
        request.state.user_role = row["role"]
        request.state.user_name = row["name"]
        request.state.user_email = row["email"]
        request.state.user_skill_level = row["skill_level"]

        return await call_next(request)
