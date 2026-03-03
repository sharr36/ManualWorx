-- Migration 006: Schematic Viewer, Diagram Annotations, and Generated Schematics

-- AI-generated annotations cached per diagram page
CREATE TABLE diagram_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    diagram_type TEXT CHECK (diagram_type IN ('hydraulic_schematic', 'electrical', 'wiring')),
    annotation_data JSONB NOT NULL,
    component_count INTEGER,
    connection_count INTEGER,
    operating_states JSONB,
    model_used TEXT,
    confidence_overall DECIMAL(4,3),
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ,
    verified_by UUID REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(page_id)
);

-- AI-generated schematics from text (not from existing diagrams)
CREATE TABLE generated_schematics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    manual_id UUID REFERENCES manuals(id) ON DELETE CASCADE,
    system_area TEXT,
    source_type TEXT CHECK (source_type IN ('text_inference', 'cross_reference', 'component_registry')),
    source_page_ids UUID[],
    diagram_dsl JSONB NOT NULL,
    svg_content TEXT,
    component_count INTEGER,
    confidence_overall DECIMAL(4,3),
    disclaimer TEXT DEFAULT 'AI-GENERATED — NOT FROM OEM MANUAL',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Physical component locations on machines
CREATE TABLE component_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    machine_model TEXT,
    component_designator TEXT,
    component_type TEXT,
    location_description TEXT,
    access_notes TEXT,
    location_image_url TEXT,
    location_coords JSONB,
    source TEXT CHECK (source IN ('manual', 'ai_inference', 'user_verified')),
    confidence DECIMAL(4,3),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_diagram_annotations_page ON diagram_annotations(page_id);
CREATE INDEX idx_diagram_annotations_tenant ON diagram_annotations(tenant_id);
CREATE INDEX idx_generated_schematics_tenant ON generated_schematics(tenant_id);
CREATE INDEX idx_generated_schematics_manual ON generated_schematics(manual_id);
CREATE INDEX idx_component_locations_tenant ON component_locations(tenant_id);
CREATE INDEX idx_component_locations_model ON component_locations(machine_model);
