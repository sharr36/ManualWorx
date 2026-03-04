"""Query and chat models."""

from pydantic import BaseModel

from manualworx_shared.constants import QueryMode


class QueryRequest(BaseModel):
    query_text: str
    query_mode: QueryMode = QueryMode.QA
    manual_ids: list[str] | None = None


class FollowupRequest(BaseModel):
    query_text: str


class SourceInfo(BaseModel):
    page_id: str
    page_number: int
    classification: str
    text_preview: str
    relevance_score: float
    manual_title: str | None = None


class ClaimResponse(BaseModel):
    id: str
    claim_text: str
    claim_type: str
    safety_critical: bool = False
    confidence_score: float = 0.0
    confidence_level: str | None = None
    sources: list = []
    corroborated: bool = False
    contradictions: list = []


class RefinementSuggestion(BaseModel):
    query: str
    reason: str


class QueryResponse(BaseModel):
    id: str
    session_id: str | None = None
    query_text: str
    query_mode: str | None = None
    response_text: str
    confidence_score: float | None = None
    confidence_level: str | None = None
    sources: list[SourceInfo] | None = None
    claims: list[ClaimResponse] | None = None
    contradiction_count: int = 0
    safety_claims: int = 0
    refinements: list[RefinementSuggestion] | None = None
    model_used: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_estimate: float | None = None
    latency_ms: int | None = None
    created_at: str | None = None


class QueryListItem(BaseModel):
    id: str
    query_text: str
    query_mode: str | None = None
    response_preview: str | None = None
    model_used: str | None = None
    latency_ms: int | None = None
    created_at: str | None = None
