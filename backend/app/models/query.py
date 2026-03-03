"""Query and chat models."""

from pydantic import BaseModel

from manualworx_shared.constants import QueryMode


class QueryRequest(BaseModel):
    query_text: str
    query_mode: QueryMode = QueryMode.QA
    manual_ids: list[str] | None = None


class FollowupRequest(BaseModel):
    query_text: str


class QueryResponse(BaseModel):
    id: str
    query_text: str
    response_text: str
    confidence_score: float | None
    sources: list[dict] | None
