-- Migration 002: Manuals, Pages, Chunks, and Shared Library

CREATE TABLE manuals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    make TEXT,
    model TEXT,
    manual_type TEXT CHECK (manual_type IN ('service', 'operator', 'parts')),
    total_pages INTEGER,
    upload_status TEXT DEFAULT 'pending' CHECK (upload_status IN ('pending', 'processing', 'ready', 'failed')),
    visibility TEXT DEFAULT 'private' CHECK (visibility IN ('private', 'shared')),
    original_pdf_url TEXT,
    processing_cost_cents INTEGER,
    our_cost_cents INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manual_id UUID NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    classification TEXT CHECK (classification IN (
        'text', 'hydraulic_schematic', 'electrical_diagram',
        'parts_exploded_view', 'torque_spec_table', 'diagnostic_flowchart',
        'wiring_harness', 'general_illustration'
    )),
    extracted_text TEXT,
    image_url TEXT,
    has_table BOOLEAN DEFAULT FALSE,
    has_diagram BOOLEAN DEFAULT FALSE,
    vector_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(manual_id, page_number)
);

CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    chunk_text TEXT NOT NULL,
    vector_id TEXT,
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Shared manual library access
CREATE TABLE tenant_manual_access (
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    manual_id UUID REFERENCES manuals(id) ON DELETE CASCADE,
    access_type TEXT DEFAULT 'full' CHECK (access_type IN ('full', 'read_only')),
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (tenant_id, manual_id)
);

-- Indexes
CREATE INDEX idx_manuals_tenant ON manuals(tenant_id);
CREATE INDEX idx_manuals_make_model ON manuals(make, model);
CREATE INDEX idx_pages_manual ON pages(manual_id);
CREATE INDEX idx_pages_classification ON pages(manual_id, classification);
CREATE INDEX idx_chunks_page ON chunks(page_id);
