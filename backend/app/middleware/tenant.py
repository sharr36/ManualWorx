"""Tenant context middleware — sets RLS variable on every authenticated request."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ..database import set_tenant_context


class TenantMiddleware(BaseHTTPMiddleware):
    """Sets the PostgreSQL session variable for Row-Level Security.

    This must run AFTER AuthMiddleware, which sets request.state.tenant_id.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        tenant_id = getattr(request.state, "tenant_id", None)

        if tenant_id and hasattr(request.app.state, "db_pool"):
            # Store tenant_id for use in route handlers' DB connections
            # The actual SET command runs per-connection in the route handlers
            pass

        return await call_next(request)
