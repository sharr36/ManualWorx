-- Migration 004: Teaching Mode, Learning Paths, and Progress Tracking

CREATE TABLE mechanics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    skill_level TEXT DEFAULT 'green' CHECK (skill_level IN ('green', 'apprentice', 'journeyman')),
    start_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE learning_paths (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    manual_id UUID REFERENCES manuals(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    system_area TEXT,
    modules JSONB,
    auto_generated BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE learning_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    mechanic_id UUID NOT NULL REFERENCES mechanics(id) ON DELETE CASCADE,
    learning_path_id UUID NOT NULL REFERENCES learning_paths(id) ON DELETE CASCADE,
    module_index INTEGER,
    lesson_index INTEGER,
    status TEXT DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'completed')),
    quiz_scores JSONB,
    time_spent_seconds INTEGER DEFAULT 0,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(mechanic_id, learning_path_id, module_index, lesson_index)
);

CREATE TABLE quiz_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    page_id UUID REFERENCES pages(id) ON DELETE SET NULL,
    question_type TEXT CHECK (question_type IN ('concept', 'diagram_id', 'scenario', 'sequence', 'safety')),
    question_text TEXT NOT NULL,
    options JSONB,
    correct_answer TEXT,
    explanation TEXT,
    difficulty TEXT CHECK (difficulty IN ('green', 'apprentice', 'journeyman')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE system_familiarity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mechanic_id UUID NOT NULL REFERENCES mechanics(id) ON DELETE CASCADE,
    machine_model TEXT,
    system_area TEXT,
    taught_at TIMESTAMPTZ,
    teach_depth TEXT CHECK (teach_depth IN ('full', 'quick', 'skipped')),
    quiz_score DECIMAL(5,2),
    troubleshoot_count INTEGER DEFAULT 0,
    last_troubleshoot_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(mechanic_id, machine_model, system_area)
);

-- Indexes
CREATE INDEX idx_mechanics_tenant ON mechanics(tenant_id);
CREATE INDEX idx_learning_paths_tenant ON learning_paths(tenant_id);
CREATE INDEX idx_learning_progress_mechanic ON learning_progress(mechanic_id);
CREATE INDEX idx_learning_progress_path ON learning_progress(learning_path_id);
CREATE INDEX idx_quiz_questions_tenant ON quiz_questions(tenant_id);
CREATE INDEX idx_quiz_questions_page ON quiz_questions(page_id);
