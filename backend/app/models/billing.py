"""Billing and usage models."""

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    plan: str  # starter, pro, shop
    success_url: str
    cancel_url: str


class PortalRequest(BaseModel):
    return_url: str


class ProcessManualPaymentRequest(BaseModel):
    manual_id: str
    page_count: int


class UsageResponse(BaseModel):
    queries_used: int
    queries_limit: int
    manuals_processed: int
    manual_limit: int
    docs_generated: int
    current_period: str
    total_ai_cost_cents: int
