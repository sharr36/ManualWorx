"""Authentication endpoints — signup, login, logout, current user."""

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from ..models.user import AuthResponse, LoginRequest, SignupRequest
from ..services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE_NAME = "manualworx_session"
SESSION_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def _set_session_cookie(response: Response, token: str, secure: bool) -> None:
    """Set the session cookie on a response."""
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=SESSION_MAX_AGE,
    )


@router.post("/signup")
async def signup(request: Request, body: SignupRequest) -> Response:
    """Create a new account (tenant + user)."""
    pool = request.app.state.db_pool
    try:
        result = await auth_service.signup(
            pool=pool,
            name=body.name,
            email=body.email,
            password=body.password,
            tenant_name=body.tenant_name,
            tenant_type=body.tenant_type,
        )
    except Exception as e:
        error_msg = str(e)
        if "unique" in error_msg.lower() and "email" in error_msg.lower():
            raise HTTPException(status_code=409, detail="Email already registered")
        if "unique" in error_msg.lower() and "slug" in error_msg.lower():
            raise HTTPException(status_code=409, detail="Organization name already taken")
        raise HTTPException(status_code=400, detail="Signup failed")

    response = JSONResponse({
        "token": result["token"],
        "user": _serialize_record(result["user"]),
        "tenant": _serialize_record(result["tenant"]),
    })
    _set_session_cookie(response, result["token"], request.url.scheme == "https")
    return response


@router.post("/login")
async def login(request: Request, body: LoginRequest) -> Response:
    """Log in with email and password."""
    pool = request.app.state.db_pool
    result = await auth_service.login(pool, body.email, body.password)

    if not result:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    response = JSONResponse({
        "token": result["token"],
        "user": _serialize_record(result["user"]),
        "tenant": _serialize_record(result["tenant"]),
    })
    _set_session_cookie(response, result["token"], request.url.scheme == "https")
    return response


@router.post("/logout")
async def logout(request: Request) -> Response:
    """Log out (delete session)."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if token:
        pool = request.app.state.db_pool
        await auth_service.logout(pool, token)

    response = JSONResponse({"status": "ok"})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/me")
async def get_current_user(request: Request) -> dict:
    """Get the current authenticated user and tenant."""
    pool = request.app.state.db_pool
    result = await auth_service.get_current_user(
        pool, request.state.user_id, request.state.tenant_id
    )

    if not result:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": _serialize_record(result["user"]),
        "tenant": _serialize_record(result["tenant"]),
    }


def _serialize_record(record: dict) -> dict:
    """Convert asyncpg Record values to JSON-serializable types."""
    result = {}
    for key, value in record.items():
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        elif hasattr(value, "hex"):  # UUID
            result[key] = str(value)
        else:
            result[key] = value
    return result
