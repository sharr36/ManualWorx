"""Interactive schematic viewer endpoints (Phase 5)."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

from ..models.viewer import (
    AnnotateRequest,
    AnnotationResponse,
    CompareRequest,
    DiagramPageItem,
    GenerateSchematicRequest,
    GenerateSchematicResponse,
    LocateComponentRequest,
    LocateComponentResponse,
)
from ..services.viewer_service import ViewerService

router = APIRouter(prefix="/api/viewer", tags=["viewer"])
_service = ViewerService()


@router.post("/annotate")
async def annotate_diagram(body: AnnotateRequest, request: Request) -> AnnotationResponse:
    """Submit a diagram page for AI annotation."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        result = await _service.annotate_diagram(
            pool, tenant_id, body.page_id, body.diagram_type
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Annotation failed for page %s: %s", body.page_id, e)
        raise HTTPException(status_code=500, detail=f"Annotation failed: {e}")

    return AnnotationResponse(**result)


@router.get("/annotations/{page_id}")
async def get_annotations(page_id: UUID, request: Request) -> AnnotationResponse:
    """Get annotations for a diagram page."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    result = await _service.get_annotations(pool, tenant_id, str(page_id))
    if not result:
        raise HTTPException(status_code=404, detail="No annotations found for this page")

    return AnnotationResponse(**result)


@router.get("/annotations/{page_id}/states")
async def get_operating_states(page_id: UUID, request: Request) -> list[dict]:
    """Get all operating states for a diagram."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    states = await _service.get_operating_states(pool, tenant_id, str(page_id))
    return states


@router.get("/annotations/{page_id}/states/{state_id}")
async def get_operating_state(page_id: UUID, state_id: str, request: Request) -> dict:
    """Get a specific operating state visualization."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    states = await _service.get_operating_states(pool, tenant_id, str(page_id))
    for state in states:
        if state.get("id") == state_id:
            return state

    raise HTTPException(status_code=404, detail="Operating state not found")


@router.get("/diagrams")
async def list_diagram_pages(
    request: Request,
    manual_id: str | None = None,
) -> list[DiagramPageItem]:
    """List all diagram pages available for the viewer."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    results = await _service.list_diagram_pages(pool, tenant_id, manual_id)
    return [DiagramPageItem(**r) for r in results]


@router.post("/generate-schematic")
async def generate_schematic(
    body: GenerateSchematicRequest, request: Request
) -> GenerateSchematicResponse:
    """Generate a clean schematic from manual pages."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        result = await _service.generate_schematic(
            pool, tenant_id, body.manual_id, body.system_area
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return GenerateSchematicResponse(**result)


@router.post("/locate-component")
async def locate_component(
    body: LocateComponentRequest, request: Request
) -> LocateComponentResponse:
    """Locate a component on the machine using manual data."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    result = await _service.locate_component(
        pool,
        tenant_id,
        body.machine_model,
        body.component_designator,
        body.manual_ids,
    )
    return LocateComponentResponse(**result)


@router.post("/compare")
async def compare_diagrams(body: CompareRequest, request: Request) -> dict:
    """Compare two diagram pages side by side."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    if len(body.page_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 page IDs required")

    result = await _service.compare_diagrams(pool, tenant_id, body.page_ids)
    return result


@router.post("/annotations/{annotation_id}/verify")
async def verify_annotation(annotation_id: UUID, request: Request) -> dict:
    """Mark an annotation as human-verified."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id

    verified = await _service.verify_annotation(
        pool, tenant_id, str(annotation_id), str(user_id)
    )
    if not verified:
        raise HTTPException(status_code=404, detail="Annotation not found")

    return {"status": "verified", "id": str(annotation_id)}
