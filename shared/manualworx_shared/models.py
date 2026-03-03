"""Shared Pydantic base models for ManualWorx."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from .constants import (
    ConfidenceLevel,
    DocumentFormat,
    DocumentType,
    ManualStatus,
    ManualType,
    PageClassification,
    QueryMode,
    SkillLevel,
    SubscriptionPlan,
    TenantType,
    UserRole,
)


class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime | None = None


class TenantBase(BaseModel):
    name: str
    type: TenantType
    slug: str


class TenantResponse(TenantBase, TimestampMixin):
    id: UUID
    subscription_plan: SubscriptionPlan
    subscription_status: str
    manual_limit: int
    user_limit: int
    query_limit_monthly: int


class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole
    skill_level: SkillLevel = SkillLevel.GREEN


class UserResponse(UserBase, TimestampMixin):
    id: UUID
    tenant_id: UUID
    last_login_at: datetime | None = None


class ManualBase(BaseModel):
    title: str
    make: str | None = None
    model: str | None = None
    manual_type: ManualType | None = None


class ManualResponse(ManualBase, TimestampMixin):
    id: UUID
    tenant_id: UUID
    total_pages: int | None = None
    upload_status: ManualStatus
    visibility: str = "private"


class PageBase(BaseModel):
    page_number: int
    classification: PageClassification | None = None
    has_table: bool = False
    has_diagram: bool = False


class PageResponse(PageBase):
    id: UUID
    manual_id: UUID
    image_url: str | None = None
    extracted_text: str | None = None


class QueryBase(BaseModel):
    query_text: str
    query_mode: QueryMode = QueryMode.AUTO
    manual_ids: list[UUID] | None = None


class QueryResponse(QueryBase, TimestampMixin):
    id: UUID
    session_id: UUID | None = None
    response_text: str | None = None
    model_used: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_estimate: float | None = None
    latency_ms: int | None = None


class DocumentBase(BaseModel):
    doc_type: DocumentType
    format: DocumentFormat = DocumentFormat.PDF


class DocumentResponse(DocumentBase, TimestampMixin):
    id: UUID
    query_id: UUID | None = None
    file_url: str | None = None


class ConfidenceScore(BaseModel):
    overall: float
    level: ConfidenceLevel
    claims: list[dict] | None = None
    gaps: list[str] | None = None


class UsageInfo(BaseModel):
    queries_used: int
    queries_limit: int
    manuals_processed: int
    manuals_limit: int
    docs_generated: int
    docs_limit: int
    period: str
