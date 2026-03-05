-- Migration 009: Performance indexes for Phase 9 polish
-- Adds composite and covering indexes for common query patterns.

-- Manuals filtered by status (upload listing, processing queue)
CREATE INDEX IF NOT EXISTS idx_manuals_tenant_status ON manuals(tenant_id, upload_status);

-- Learning progress ordered by recency (dashboard, progress reports)
CREATE INDEX IF NOT EXISTS idx_learning_progress_created ON learning_progress(mechanic_id, created_at DESC);

-- System familiarity lookups by mechanic + model (teach mode)
CREATE INDEX IF NOT EXISTS idx_system_familiarity_mechanic ON system_familiarity(mechanic_id, machine_model);

-- Documentation coverage lookups by manual (analysis page)
CREATE INDEX IF NOT EXISTS idx_documentation_coverage_manual ON documentation_coverage(manual_id);

-- Sessions by expiry (auth middleware hot path — used to find/prune expired sessions)
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- Chunks vector_id lookups (retrieval service reverse-mapping)
CREATE INDEX IF NOT EXISTS idx_chunks_vector_id ON chunks(vector_id) WHERE vector_id IS NOT NULL;

-- Pages with diagrams (schematic viewer listing)
CREATE INDEX IF NOT EXISTS idx_pages_has_diagram ON pages(manual_id) WHERE has_diagram = TRUE;
