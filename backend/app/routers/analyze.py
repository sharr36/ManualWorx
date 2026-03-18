"""Confidence analysis and inference endpoints (Phase 6)."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..services.confidence_service import ConfidenceService
from ..services.inference_service import InferenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analyze", tags=["analysis"])
_inference = InferenceService()
_confidence = ConfidenceService()


class DiagramAnalyzeRequest(BaseModel):
    page_id: str
    manual_id: str | None = None


class TextAnalyzeRequest(BaseModel):
    page_id: str


class AggregateRequest(BaseModel):
    manual_id: str
    system_area: str | None = None


class CoverageRequest(BaseModel):
    manual_id: str
    system_area: str | None = None


class ComponentInferRequest(BaseModel):
    manual_id: str
    system_area: str | None = None


class GapDetectRequest(BaseModel):
    manual_id: str


@router.post("/diagram")
async def analyze_diagram(body: DiagramAnalyzeRequest, request: Request) -> dict:
    """Analyze a diagram page and return inferred components."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        result = await _inference.infer_components(
            pool, tenant_id, body.manual_id or body.page_id, None
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result


@router.post("/text")
async def analyze_text(body: TextAnalyzeRequest, request: Request) -> dict:
    """Analyze text content for specs, safety warnings, and procedures."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        result = await _inference.analyze_text(pool, tenant_id, body.page_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result


@router.post("/aggregate")
async def aggregate_analysis(body: AggregateRequest, request: Request) -> dict:
    """Aggregate analysis across multiple pages for a system area."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        result = await _inference.aggregate_analysis(
            pool, tenant_id, body.manual_id, body.system_area
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result


@router.get("/confidence/{query_id}")
async def get_confidence(query_id: UUID, request: Request) -> dict:
    """Get per-claim confidence breakdown for a query response."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    claims = await _confidence.get_claim_breakdown(pool, tenant_id, query_id)
    if not claims:
        raise HTTPException(status_code=404, detail="No claims found for this query")

    overall = _confidence.aggregate_confidence([
        {"confidence": c["confidence_score"], "safety_critical": c["safety_critical"]}
        for c in claims
    ])

    return {
        "query_id": str(query_id),
        "claims": claims,
        "overall_confidence": overall,
        "claim_count": len(claims),
        "safety_claims": sum(1 for c in claims if c["safety_critical"]),
        "contradiction_count": sum(
            1 for c in claims if c.get("contradictions")
        ),
    }


@router.post("/coverage")
async def analyze_coverage(body: CoverageRequest, request: Request) -> dict:
    """Analyze documentation coverage for a system area."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        result = await _inference.analyze_coverage(
            pool, tenant_id, body.manual_id, body.system_area
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result


@router.post("/components")
async def infer_components(body: ComponentInferRequest, request: Request) -> dict:
    """Extract and infer components from manual pages."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        result = await _inference.infer_components(
            pool, tenant_id, body.manual_id, body.system_area
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Component inference failed for manual %s: %s", body.manual_id, e)
        raise HTTPException(status_code=500, detail=f"Component inference failed: {e}")

    return result


@router.post("/gaps")
async def detect_gaps(body: GapDetectRequest, request: Request) -> dict:
    """Detect documentation gaps in a manual."""
    pool = request.app.state.db_pool
    tenant_id = request.state.tenant_id

    try:
        result = await _inference.detect_gaps(pool, tenant_id, body.manual_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Gap detection failed for manual %s: %s", body.manual_id, e)
        raise HTTPException(status_code=500, detail=f"Gap detection failed: {e}")

    return result
