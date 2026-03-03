#!/usr/bin/env bash
set -euo pipefail

# ManualWorx — Seed development database
# Creates a test tenant and user for local development.

DATABASE_URL="${DATABASE_URL:-postgresql://manualworx:password@localhost:5432/manualworx}"

echo "=== Seeding dev database ==="

psql "$DATABASE_URL" << 'SQL'
-- Create test tenant
INSERT INTO tenants (id, type, name, slug, subscription_plan, subscription_status, manual_limit, user_limit, query_limit_monthly)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'shop',
    'Test Shop',
    'test-shop',
    'pro',
    'active',
    50, 10, 1000
)
ON CONFLICT (slug) DO NOTHING;

-- Create test user (password: "testpassword123")
-- argon2 hash of "testpassword123"
INSERT INTO users (id, tenant_id, email, name, password_hash, role, skill_level)
VALUES (
    'b0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001',
    'test@manualworx.dev',
    'Test User',
    '$argon2id$v=19$m=65536,t=3,p=4$placeholder$hash',
    'owner',
    'journeyman'
)
ON CONFLICT DO NOTHING;

SELECT 'Seeded: tenant=' || t.name || ', user=' || u.email
FROM tenants t, users u
WHERE t.id = 'a0000000-0000-0000-0000-000000000001'
  AND u.id = 'b0000000-0000-0000-0000-000000000001';
SQL

echo "=== Dev seed complete ==="
echo "Login with: test@manualworx.dev / testpassword123"
