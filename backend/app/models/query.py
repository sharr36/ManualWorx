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


class QueryResponse(BaseModel):
    id: str
    session_id: str | None = None
    query_text: str
    query_mode: str | None = None
    response_text: str
    confidence_score: float | None = None
    confidence_level: str | None = None
    sources: list[SourceInfo] | None = None
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
