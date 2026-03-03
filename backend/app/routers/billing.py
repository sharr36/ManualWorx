"""Billing and subscription endpoints."""

import json

from fastapi import APIRouter, HTTPException, Request

from ..models.billing import CheckoutRequest, PortalRequest, ProcessManualPaymentRequest
from ..services import billing_service

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/checkout")
async def create_checkout(request: Request, body: CheckoutRequest) -> dict:
    """Create a Stripe Checkout session for plan upgrade."""
    if request.state.user_role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can manage billing")

    pool = request.app.state.db_pool
    try:
        result = await billing_service.create_checkout_session(
            pool,
            request.state.tenant_id,
            plan=body.plan,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    return result


@router.post("/portal")
async def create_portal(request: Request, body: PortalRequest) -> dict:
    """Create a Stripe Customer Portal session."""
    if request.state.user_role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can manage billing")

    pool = request.app.state.db_pool
    try:
        result = await billing_service.create_portal_session(
            pool, request.state.tenant_id, return_url=body.return_url
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@router.get("/usage")
async def get_usage(request: Request) -> dict:
    """Get usage for the current billing period."""
    pool = request.app.state.db_pool
    return await billing_service.get_usage(pool, request.state.tenant_id)


@router.post("/process-manual")
async def create_manual_payment(request: Request, body: ProcessManualPaymentRequest) -> dict:
    """Create a payment intent for manual processing fee."""
    if request.state.user_role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can manage billing")

    pool = request.app.state.db_pool
    try:
        result = await billing_service.create_manual_payment_intent(
            pool, request.state.tenant_id, page_count=body.page_count
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


# Stripe webhook — separate router for webhook path
webhook_router = APIRouter(tags=["webhooks"])


@webhook_router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict:
    """Handle Stripe webhook events."""
    import stripe

    from ..config import settings

    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    pool = request.app.state.db_pool
    await billing_service.handle_webhook(pool, event["type"], event["data"]["object"])

    return {"status": "ok"}
