-- Migration 001: Tenants, Users, and Sessions
-- Core multi-tenancy tables

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Tenants (the billing and isolation entity)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL CHECK (type IN ('shop', 'individual')),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    owner_user_id UUID,  -- Set after first user is created
    stripe_customer_id TEXT,
    subscription_plan TEXT DEFAULT 'free' CHECK (subscription_plan IN ('free', 'starter', 'pro', 'shop')),
    subscription_status TEXT DEFAULT 'active' CHECK (subscription_status IN ('active', 'past_due', 'canceled', 'trialing')),
    manual_limit INTEGER DEFAULT 2,
    user_limit INTEGER DEFAULT 1,
    query_limit_monthly INTEGER DEFAULT 25,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users belong to a tenant
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'manager', 'technician')),
    skill_level TEXT DEFAULT 'green' CHECK (skill_level IN ('green', 'apprentice', 'journeyman')),
    auth_provider TEXT DEFAULT 'email' CHECK (auth_provider IN ('email', 'google')),
    auth_id TEXT,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Set the foreign key for tenant owner
ALTER TABLE tenants ADD CONSTRAINT fk_tenants_owner
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL;

-- Sessions for auth
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_sessions_token ON sessions(token_hash);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
CREATE INDEX idx_tenants_slug ON tenants(slug);
CREATE INDEX idx_tenants_active ON tenants(id) WHERE subscription_status = 'active';
