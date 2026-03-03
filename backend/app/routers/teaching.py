"""Teaching mode and learning path endpoints (Phase 8)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..models.teaching import (
    AssistRequest,
    QuizGenerateRequest,
    QuizSubmitRequest,
    TeachRequest,
)

router = APIRouter(tags=["teaching"])


# --- Teaching endpoints ---

@router.post("/api/teach/explain")
async def explain_system(body: TeachRequest) -> dict:
    """Explain a system area from a manual (lesson mode)."""
    raise HTTPException(status_code=501, detail="Teaching mode coming in Phase 8")


@router.post("/api/teach/walkthrough")
async def system_walkthrough(body: TeachRequest) -> dict:
    """Interactive system walkthrough with diagrams."""
    raise HTTPException(status_code=501, detail="Teaching mode coming in Phase 8")


@router.post("/api/teach/quiz/generate")
async def generate_quiz(body: QuizGenerateRequest) -> dict:
    """Generate quiz questions for a learning module."""
    raise HTTPException(status_code=501, detail="Quiz generation coming in Phase 8")


@router.post("/api/teach/quiz/submit")
async def submit_quiz(body: QuizSubmitRequest) -> dict:
    """Submit quiz answers and get scored results."""
    raise HTTPException(status_code=501, detail="Quiz submission coming in Phase 8")


# --- Teach-then-troubleshoot assist endpoints ---

@router.post("/api/assist")
async def start_assist(body: AssistRequest) -> dict:
    """Start a teach-then-troubleshoot session."""
    raise HTTPException(status_code=501, detail="Assist mode coming in Phase 8")


@router.post("/api/assist/{session_id}/choice")
async def assist_choice(session_id: UUID, body: dict) -> dict:
    """User selects teach-first, quick overview, or skip-to-fix."""
    raise HTTPException(status_code=501, detail="Assist mode coming in Phase 8")


@router.post("/api/assist/{session_id}/continue")
async def assist_continue(session_id: UUID) -> dict:
    """Continue the assist session after teaching."""
    raise HTTPException(status_code=501, detail="Assist mode coming in Phase 8")


# --- Learning path endpoints ---

@router.post("/api/paths/generate")
async def generate_learning_path(body: dict) -> dict:
    """Auto-generate a learning path from a manual."""
    raise HTTPException(status_code=501, detail="Learning paths coming in Phase 8")


@router.get("/api/paths")
async def list_learning_paths() -> list[dict]:
    """List learning paths for the tenant."""
    raise HTTPException(status_code=501, detail="Learning paths coming in Phase 8")


@router.get("/api/paths/{path_id}")
async def get_learning_path(path_id: UUID) -> dict:
    """Get a learning path and its modules."""
    raise HTTPException(status_code=501, detail="Learning paths coming in Phase 8")


@router.get("/api/paths/{path_id}/progress/{mechanic_id}")
async def get_learning_progress(path_id: UUID, mechanic_id: UUID) -> dict:
    """Get a mechanic's progress on a learning path."""
    raise HTTPException(status_code=501, detail="Learning progress coming in Phase 8")


# --- Mechanic management ---

@router.post("/api/mechanics")
async def create_mechanic(body: dict) -> dict:
    """Register a mechanic profile for learning tracking."""
    raise HTTPException(status_code=501, detail="Mechanic profiles coming in Phase 8")


@router.get("/api/mechanics/{mechanic_id}/dashboard")
async def mechanic_dashboard(mechanic_id: UUID) -> dict:
    """Get a mechanic's learning dashboard."""
    raise HTTPException(status_code=501, detail="Mechanic dashboard coming in Phase 8")
