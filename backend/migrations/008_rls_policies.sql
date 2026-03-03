-- Migration 008: Row-Level Security Policies
-- Every tenant-scoped table gets RLS to prevent cross-tenant data leakage.
-- The application middleware sets: SET app.current_tenant_id = '{uuid}'

-- Migration tracking table (no RLS needed)
CREATE TABLE IF NOT EXISTS _migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Enable RLS on all tenant-scoped tables
-- ============================================================

-- Tenants: users can only see their own tenant
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_self_access ON tenants
    USING (id = current_setting('app.current_tenant_id', true)::UUID);

-- Users: scoped to tenant
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Sessions: scoped via user's tenant
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON sessions
    USING (user_id IN (
        SELECT id FROM users
        WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
    ));

-- Manuals: scoped to tenant (includes shared manuals via tenant_manual_access)
ALTER TABLE manuals ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON manuals
    USING (
        tenant_id = current_setting('app.current_tenant_id', true)::UUID
        OR id IN (
            SELECT manual_id FROM tenant_manual_access
            WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
        )
    );

-- Pages: scoped via manual's tenant
ALTER TABLE pages ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON pages
    USING (manual_id IN (
        SELECT id FROM manuals
        WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
        OR id IN (
            SELECT manual_id FROM tenant_manual_access
            WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
        )
    ));

-- Chunks: scoped via page's manual's tenant
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON chunks
    USING (page_id IN (
        SELECT p.id FROM pages p
        JOIN manuals m ON p.manual_id = m.id
        WHERE m.tenant_id = current_setting('app.current_tenant_id', true)::UUID
    ));

-- Queries: scoped to tenant
ALTER TABLE queries ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON queries
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Documents: scoped to tenant
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Mechanics: scoped to tenant
ALTER TABLE mechanics ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON mechanics
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Learning paths: scoped to tenant
ALTER TABLE learning_paths ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON learning_paths
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Learning progress: scoped to tenant
ALTER TABLE learning_progress ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON learning_progress
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Quiz questions: scoped to tenant
ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON quiz_questions
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Response claims: scoped to tenant
ALTER TABLE response_claims ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON response_claims
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Documentation coverage: scoped to tenant
ALTER TABLE documentation_coverage ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documentation_coverage
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Inferred components: scoped to tenant
ALTER TABLE inferred_components ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inferred_components
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Diagram annotations: scoped to tenant
ALTER TABLE diagram_annotations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON diagram_annotations
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Generated schematics: scoped to tenant
ALTER TABLE generated_schematics ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON generated_schematics
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Component locations: scoped to tenant
ALTER TABLE component_locations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON component_locations
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Billing events: scoped to tenant
ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON billing_events
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Usage tracking: scoped to tenant
ALTER TABLE usage_tracking ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON usage_tracking
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- Tenant manual access: scoped to tenant
ALTER TABLE tenant_manual_access ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenant_manual_access
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- ============================================================
-- Note: system_familiarity does NOT have tenant_id directly.
-- It's scoped via mechanic_id → mechanics.tenant_id.
-- RLS is enforced through the mechanics table join.
-- ============================================================
ALTER TABLE system_familiarity ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON system_familiarity
    USING (mechanic_id IN (
        SELECT id FROM mechanics
        WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
    ));
