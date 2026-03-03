-- Migration 003: Queries and Documents

CREATE TABLE queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    session_id UUID,
    query_text TEXT NOT NULL,
    query_mode TEXT CHECK (query_mode IN ('auto', 'qa', 'troubleshoot', 'diagram', 'procedure')),
    manual_ids UUID[],
    retrieved_page_ids UUID[],
    model_used TEXT,
    response_text TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_estimate DECIMAL(10,6),
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    query_id UUID REFERENCES queries(id) ON DELETE SET NULL,
    doc_type TEXT CHECK (doc_type IN (
        'troubleshooting_guide', 'service_procedure', 'parts_reference',
        'quick_reference', 'training_lesson', 'quiz_assessment',
        'progress_report', 'system_analysis', 'gap_report'
    )),
    format TEXT CHECK (format IN ('pdf', 'docx')),
    file_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_queries_tenant_created ON queries(tenant_id, created_at DESC);
CREATE INDEX idx_queries_session ON queries(session_id);
CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_query ON documents(query_id);
