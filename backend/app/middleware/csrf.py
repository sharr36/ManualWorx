"""CSRF protection using the double-submit cookie pattern."""

import logging
import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_TOKEN_LENGTH = 32

# Paths exempt from CSRF checks (webhooks, health, auth reads, docs)
CSRF_EXEMPT_PATHS = frozenset({
    "/api/health",
    "/api/billing/webhook",
    "/docs",
    "/redoc",
    "/openapi.json",
})

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF protection.

    Safe methods (GET/HEAD/OPTIONS): set a csrf_token cookie if not present.
    Mutating methods (POST/PUT/PATCH/DELETE): require X-CSRF-Token header
    matching the csrf_token cookie value.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip exempt paths
        if any(path.startswith(p) for p in CSRF_EXEMPT_PATHS):
            return await call_next(request)

        # Safe methods: ensure CSRF cookie exists
        if request.method in SAFE_METHODS:
            response = await call_next(request)
            if CSRF_COOKIE_NAME not in request.cookies:
                token = secrets.token_urlsafe(CSRF_TOKEN_LENGTH)
                response.set_cookie(
                    CSRF_COOKIE_NAME,
                    token,
                    httponly=False,  # JS must read this
                    secure=request.url.scheme == "https",
                    samesite="lax",
                    path="/",
                    max_age=86400,
                )
            return response

        # Mutating methods: validate CSRF token
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token:
            logger.warning("CSRF: missing token (path=%s)", path)
            return JSONResponse(
                {"detail": "CSRF token missing"},
                status_code=403,
            )

        if not secrets.compare_digest(cookie_token, header_token):
            logger.warning("CSRF: token mismatch (path=%s)", path)
            return JSONResponse(
                {"detail": "CSRF token invalid"},
                status_code=403,
            )

        return await call_next(request)
