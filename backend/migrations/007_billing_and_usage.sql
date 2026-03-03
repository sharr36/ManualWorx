-- Migration 007: Billing Events and Usage Tracking

CREATE TABLE billing_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'subscription_created', 'subscription_upgraded', 'subscription_downgraded',
        'subscription_canceled', 'manual_processed', 'query_overage',
        'payment_succeeded', 'payment_failed'
    )),
    stripe_event_id TEXT,
    amount_cents INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE usage_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    period TEXT NOT NULL,  -- "2026-03"
    queries_used INTEGER DEFAULT 0,
    queries_limit INTEGER NOT NULL,
    manuals_processed INTEGER DEFAULT 0,
    docs_generated INTEGER DEFAULT 0,
    total_ai_cost_cents INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, period)
);

-- Indexes
CREATE INDEX idx_billing_events_tenant ON billing_events(tenant_id);
CREATE INDEX idx_billing_events_type ON billing_events(event_type);
CREATE INDEX idx_billing_events_created ON billing_events(created_at DESC);
CREATE INDEX idx_usage_tenant_period ON usage_tracking(tenant_id, period);
