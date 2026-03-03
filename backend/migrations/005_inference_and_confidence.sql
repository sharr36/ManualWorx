-- Migration 005: Inference Engine and Confidence Scoring

-- Per-claim source attribution and confidence tracking
CREATE TABLE response_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    query_id UUID REFERENCES queries(id) ON DELETE CASCADE,
    claim_text TEXT NOT NULL,
    claim_type TEXT CHECK (claim_type IN ('spec', 'description', 'procedure_step', 'warning')),
    safety_critical BOOLEAN DEFAULT FALSE,
    confidence_score DECIMAL(4,3),
    confidence_level TEXT CHECK (confidence_level IN ('high', 'moderate', 'low', 'inference')),
    sources JSONB,
    corroborated BOOLEAN DEFAULT FALSE,
    contradictions JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Track documentation coverage per manual/system
CREATE TABLE documentation_coverage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    manual_id UUID REFERENCES manuals(id) ON DELETE CASCADE,
    machine_model TEXT,
    system_area TEXT,
    has_service_manual BOOLEAN DEFAULT FALSE,
    has_operator_manual BOOLEAN DEFAULT FALSE,
    has_parts_manual BOOLEAN DEFAULT FALSE,
    has_hydraulic_schematic BOOLEAN DEFAULT FALSE,
    has_electrical_schematic BOOLEAN DEFAULT FALSE,
    has_wiring_diagram BOOLEAN DEFAULT FALSE,
    has_diagnostic_flowchart BOOLEAN DEFAULT FALSE,
    coverage_score DECIMAL(4,3),
    gaps JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Components inferred from diagrams or text
CREATE TABLE inferred_components (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    manual_id UUID REFERENCES manuals(id) ON DELETE CASCADE,
    system_area TEXT,
    component_name TEXT,
    component_type TEXT,
    designator TEXT,
    inferred_from TEXT CHECK (inferred_from IN ('diagram', 'manual_text', 'cross_reference', 'ai_knowledge')),
    confidence_score DECIMAL(4,3),
    specs JSONB,
    spec_sources JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_response_claims_query ON response_claims(query_id);
CREATE INDEX idx_response_claims_tenant ON response_claims(tenant_id);
CREATE INDEX idx_documentation_coverage_tenant ON documentation_coverage(tenant_id);
CREATE INDEX idx_inferred_components_tenant ON inferred_components(tenant_id);
CREATE INDEX idx_inferred_components_manual ON inferred_components(manual_id);
