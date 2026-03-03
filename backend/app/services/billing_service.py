"""Stripe billing integration service."""

from uuid import UUID

import asyncpg

from manualworx_shared.constants import PLAN_CONFIG, PROCESSING_FEES


async def create_checkout_session(
    pool: asyncpg.Pool,
    tenant_id: UUID,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Create a Stripe Checkout session for subscription upgrade."""
    import stripe

    from ..config import settings

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Get the tenant's Stripe customer ID
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stripe_customer_id, slug, name FROM tenants WHERE id = $1",
            tenant_id,
        )

    if not row:
        raise ValueError("Tenant not found")

    customer_id = row["stripe_customer_id"]

    # Create customer if not exists
    if not customer_id:
        customer = stripe.Customer.create(
            name=row["name"],
            metadata={"tenant_id": str(tenant_id), "slug": row["slug"]},
        )
        customer_id = customer.id
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE tenants SET stripe_customer_id = $1 WHERE id = $2",
                customer_id,
                tenant_id,
            )

    # Map plan to price ID
    price_map = {
        "starter": settings.STRIPE_PRICE_STARTER_MONTHLY,
        "pro": settings.STRIPE_PRICE_PRO_MONTHLY,
        "shop": settings.STRIPE_PRICE_SHOP_BASE_MONTHLY,
    }
    price_id = price_map.get(plan)
    if not price_id:
        raise ValueError(f"Unknown plan: {plan}")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"tenant_id": str(tenant_id)},
    )

    return {"session_url": session.url, "session_id": session.id}


async def create_portal_session(
    pool: asyncpg.Pool,
    tenant_id: UUID,
    return_url: str,
) -> dict:
    """Create a Stripe Customer Portal session."""
    import stripe

    from ..config import settings

    stripe.api_key = settings.STRIPE_SECRET_KEY

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stripe_customer_id FROM tenants WHERE id = $1",
            tenant_id,
        )

    if not row or not row["stripe_customer_id"]:
        raise ValueError("No billing account found")

    session = stripe.billing_portal.Session.create(
        customer=row["stripe_customer_id"],
        return_url=return_url,
    )

    return {"portal_url": session.url}


async def get_usage(pool: asyncpg.Pool, tenant_id: UUID) -> dict:
    """Get current billing period usage for a tenant."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT queries_used, queries_limit, manuals_processed,
                   docs_generated, total_ai_cost_cents, period
            FROM usage_tracking
            WHERE tenant_id = $1
            ORDER BY period DESC
            LIMIT 1
            """,
            tenant_id,
        )

        tenant = await conn.fetchrow(
            "SELECT manual_limit, query_limit_monthly FROM tenants WHERE id = $1",
            tenant_id,
        )

    if not row:
        return {
            "queries_used": 0,
            "queries_limit": tenant["query_limit_monthly"] if tenant else 0,
            "manuals_processed": 0,
            "manual_limit": tenant["manual_limit"] if tenant else 0,
            "docs_generated": 0,
            "current_period": "",
            "total_ai_cost_cents": 0,
        }

    return {
        "queries_used": row["queries_used"],
        "queries_limit": row["queries_limit"],
        "manuals_processed": row["manuals_processed"],
        "manual_limit": tenant["manual_limit"] if tenant else 0,
        "docs_generated": row["docs_generated"],
        "current_period": row["period"].isoformat() if row["period"] else "",
        "total_ai_cost_cents": row["total_ai_cost_cents"],
    }


async def create_manual_payment_intent(
    pool: asyncpg.Pool,
    tenant_id: UUID,
    page_count: int,
) -> dict:
    """Create a payment intent for one-time manual processing fee."""
    import stripe

    from ..config import settings

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Calculate price based on page count tiers
    amount_cents = _calculate_processing_fee(page_count)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stripe_customer_id FROM tenants WHERE id = $1",
            tenant_id,
        )

    if not row or not row["stripe_customer_id"]:
        raise ValueError("No billing account found")

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        customer=row["stripe_customer_id"],
        metadata={
            "tenant_id": str(tenant_id),
            "type": "manual_processing",
            "page_count": str(page_count),
        },
    )

    return {
        "client_secret": intent.client_secret,
        "amount_cents": amount_cents,
    }


def _calculate_processing_fee(page_count: int) -> int:
    """Calculate the processing fee in cents based on page count tiers."""
    for tier in PROCESSING_FEES:
        if page_count <= tier["max_pages"]:
            return tier["price_cents"]
    # Use the highest tier for very large manuals
    return PROCESSING_FEES[-1]["price_cents"]


async def handle_webhook(pool: asyncpg.Pool, event_type: str, event_data: dict) -> None:
    """Handle a Stripe webhook event."""
    plan_map = {
        "starter": "starter",
        "pro": "pro",
        "shop": "shop",
    }

    if event_type == "customer.subscription.created":
        await _handle_subscription_change(pool, event_data, "active")
    elif event_type == "customer.subscription.updated":
        status = event_data.get("status", "active")
        await _handle_subscription_change(pool, event_data, status)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_change(pool, event_data, "canceled")
    elif event_type == "invoice.payment_succeeded":
        await _record_billing_event(pool, event_data, "payment_succeeded")
    elif event_type == "invoice.payment_failed":
        await _record_billing_event(pool, event_data, "payment_failed")


async def _handle_subscription_change(
    pool: asyncpg.Pool, event_data: dict, status: str
) -> None:
    """Update tenant subscription status from Stripe event."""
    customer_id = event_data.get("customer")
    if not customer_id:
        return

    # Determine the plan from price ID
    items = event_data.get("items", {}).get("data", [])
    plan = "free"
    if items:
        price_id = items[0].get("price", {}).get("id", "")
        from ..config import settings

        if price_id == settings.STRIPE_PRICE_STARTER_MONTHLY:
            plan = "starter"
        elif price_id == settings.STRIPE_PRICE_PRO_MONTHLY:
            plan = "pro"
        elif price_id == settings.STRIPE_PRICE_SHOP_BASE_MONTHLY:
            plan = "shop"

    plan_config = PLAN_CONFIG.get(plan, PLAN_CONFIG["free"])

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE tenants
            SET subscription_plan = $1,
                subscription_status = $2,
                manual_limit = $3,
                user_limit = $4,
                query_limit_monthly = $5,
                updated_at = NOW()
            WHERE stripe_customer_id = $6
            """,
            plan,
            status,
            plan_config["manual_limit"],
            plan_config["user_limit"],
            plan_config["query_limit"],
            customer_id,
        )


async def _record_billing_event(
    pool: asyncpg.Pool, event_data: dict, event_type: str
) -> None:
    """Record a billing event for audit trail."""
    customer_id = event_data.get("customer")
    amount = event_data.get("amount_paid", 0)

    async with pool.acquire() as conn:
        tenant = await conn.fetchrow(
            "SELECT id FROM tenants WHERE stripe_customer_id = $1",
            customer_id,
        )
        if tenant:
            await conn.execute(
                """
                INSERT INTO billing_events (tenant_id, event_type, amount_cents, metadata)
                VALUES ($1, $2, $3, $4)
                """,
                tenant["id"],
                event_type,
                amount,
                str(event_data),
            )
