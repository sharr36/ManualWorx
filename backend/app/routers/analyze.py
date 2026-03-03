"""Confidence analysis and inference endpoints (Phase 6)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/analyze", tags=["analysis"])


@router.post("/diagram")
async def analyze_diagram(body: dict) -> dict:
    """Analyze a diagram page and return inferred components."""
    raise HTTPException(status_code=501, detail="Diagram analysis coming in Phase 6")


@router.post("/text")
async def analyze_text(body: dict) -> dict:
    """Analyze text content for specs, safety warnings, and procedures."""
    raise HTTPException(status_code=501, detail="Text analysis coming in Phase 6")


@router.post("/aggregate")
async def aggregate_analysis(body: dict) -> dict:
    """Aggregate analysis across multiple pages for a system area."""
    raise HTTPException(status_code=501, detail="Aggregate analysis coming in Phase 6")


@router.get("/confidence/{query_id}")
async def get_confidence(query_id: UUID) -> dict:
    """Get per-claim confidence breakdown for a query response."""
    raise HTTPException(status_code=501, detail="Confidence analysis coming in Phase 6")
