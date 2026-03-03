"""Interactive schematic viewer endpoints (Phase 5)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..models.viewer import (
    AnnotateRequest,
    CompareRequest,
    GenerateSchematicRequest,
    LocateComponentRequest,
)

router = APIRouter(prefix="/api/viewer", tags=["viewer"])


@router.post("/annotate")
async def annotate_diagram(body: AnnotateRequest) -> dict:
    """Submit a diagram page for AI annotation."""
    raise HTTPException(status_code=501, detail="Diagram annotation coming in Phase 5")


@router.get("/annotations/{page_id}")
async def get_annotations(page_id: UUID) -> dict:
    """Get annotations for a diagram page."""
    raise HTTPException(status_code=501, detail="Diagram annotations coming in Phase 5")


@router.get("/annotations/{page_id}/states")
async def get_operating_states(page_id: UUID) -> list[dict]:
    """Get all operating states for a diagram."""
    raise HTTPException(status_code=501, detail="Operating states coming in Phase 5")


@router.get("/annotations/{page_id}/states/{state_id}")
async def get_operating_state(page_id: UUID, state_id: str) -> dict:
    """Get a specific operating state visualization."""
    raise HTTPException(status_code=501, detail="Operating states coming in Phase 5")


@router.post("/generate-schematic")
async def generate_schematic(body: GenerateSchematicRequest) -> dict:
    """Generate a clean schematic from manual pages."""
    raise HTTPException(status_code=501, detail="Schematic generation coming in Phase 5")


@router.post("/locate-component")
async def locate_component(body: LocateComponentRequest) -> dict:
    """Locate a component on the machine using manual data."""
    raise HTTPException(status_code=501, detail="Component location coming in Phase 5")


@router.post("/compare")
async def compare_diagrams(body: CompareRequest) -> dict:
    """Compare two diagram pages side by side."""
    raise HTTPException(status_code=501, detail="Diagram comparison coming in Phase 5")


@router.post("/annotations/{annotation_id}/verify")
async def verify_annotation(annotation_id: UUID, body: dict) -> dict:
    """Mark an annotation as human-verified."""
    raise HTTPException(status_code=501, detail="Annotation verification coming in Phase 5")
