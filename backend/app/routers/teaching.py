"""Teaching mode and learning path endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from ..models.teaching import (
    AssistChoiceRequest,
    AssistRequest,
    CreateMechanicRequest,
    GeneratePathRequest,
    QuizGenerateRequest,
    QuizSubmitRequest,
    TeachRequest,
)
from ..services.teaching_service import TeachingService

router = APIRouter(tags=["teaching"])
_service = TeachingService()


# --- Teaching endpoints ---


@router.post("/api/teach/explain")
async def explain_system(body: TeachRequest, request: Request) -> dict:
    """Explain a system area from a manual (lesson mode)."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    return await _service.explain_system(
        pool, tenant_id, body.manual_id, body.system_area, depth=body.depth.value
    )


@router.post("/api/teach/walkthrough")
async def system_walkthrough(body: TeachRequest, request: Request) -> dict:
    """Interactive system walkthrough with diagrams."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    return await _service.system_walkthrough(
        pool, tenant_id, body.manual_id, body.system_area
    )


@router.post("/api/teach/quiz/generate")
async def generate_quiz(body: QuizGenerateRequest, request: Request) -> dict:
    """Generate quiz questions for a learning module."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    return await _service.generate_quiz(
        pool, tenant_id, UUID(body.learning_path_id), body.module_index, count=body.count
    )


@router.post("/api/teach/quiz/submit")
async def submit_quiz(body: QuizSubmitRequest, request: Request) -> dict:
    """Submit quiz answers and get scored results."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    return await _service.submit_quiz(
        pool,
        tenant_id,
        UUID(body.learning_path_id),
        body.module_index,
        body.answers,
        mechanic_id=UUID(body.mechanic_id) if body.mechanic_id else None,
    )


# --- Teach-then-troubleshoot assist endpoints ---


@router.post("/api/assist")
async def start_assist(body: AssistRequest, request: Request) -> dict:
    """Start a teach-then-troubleshoot session."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    return await _service.start_assist(
        pool, tenant_id, body.problem_description,
        machine_model=body.machine_model,
        manual_ids=body.manual_ids,
    )


@router.post("/api/assist/{session_id}/choice")
async def assist_choice(
    session_id: UUID, body: AssistChoiceRequest, request: Request
) -> dict:
    """User selects teach-first, quick overview, or skip-to-fix."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        return await _service.assist_choice(
            pool, tenant_id, session_id, body.choice,
            mechanic_id=UUID(body.mechanic_id) if body.mechanic_id else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/assist/{session_id}/continue")
async def assist_continue(session_id: UUID, request: Request) -> dict:
    """Continue the assist session after teaching."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        return await _service.assist_continue(pool, tenant_id, session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Learning path endpoints ---


@router.post("/api/paths/generate")
async def generate_learning_path(body: GeneratePathRequest, request: Request) -> dict:
    """Auto-generate a learning path from a manual."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        return await _service.generate_learning_path(pool, tenant_id, body.manual_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/paths")
async def list_learning_paths(request: Request) -> list[dict]:
    """List learning paths for the tenant."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    return await _service.list_learning_paths(pool, tenant_id)


@router.get("/api/paths/{path_id}")
async def get_learning_path(path_id: UUID, request: Request) -> dict:
    """Get a learning path and its modules."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    result = await _service.get_learning_path(pool, tenant_id, path_id)
    if not result:
        raise HTTPException(status_code=404, detail="Learning path not found")
    return result


@router.get("/api/paths/{path_id}/progress/{mechanic_id}")
async def get_learning_progress(
    path_id: UUID, mechanic_id: UUID, request: Request
) -> dict:
    """Get a mechanic's progress on a learning path."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        return await _service.get_learning_progress(pool, tenant_id, path_id, mechanic_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Mechanic management ---


@router.post("/api/mechanics")
async def create_mechanic(body: CreateMechanicRequest, request: Request) -> dict:
    """Register a mechanic profile for learning tracking."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    return await _service.create_mechanic(
        pool, tenant_id, body.name,
        user_id=UUID(body.user_id) if body.user_id else None,
        skill_level=body.skill_level.value,
    )


@router.get("/api/mechanics/{mechanic_id}/dashboard")
async def mechanic_dashboard(mechanic_id: UUID, request: Request) -> dict:
    """Get a mechanic's learning dashboard."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        return await _service.get_mechanic_dashboard(pool, tenant_id, mechanic_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
