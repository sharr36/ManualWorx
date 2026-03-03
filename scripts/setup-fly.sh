#!/usr/bin/env bash
set -euo pipefail

# ManualWorx — Fly.io infrastructure setup
# Run this once to create all Fly apps and backing services.

echo "=== ManualWorx Fly.io Setup ==="
echo ""

# Check flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "Error: flyctl not found. Install from https://fly.io/docs/flyctl/install/"
    exit 1
fi

# Check logged in
flyctl auth whoami || { echo "Please run: flyctl auth login"; exit 1; }

echo ""
echo "--- Creating Fly apps ---"

# API
flyctl apps create manualworx-api --org personal 2>/dev/null || echo "manualworx-api already exists"

# Web frontend
flyctl apps create manualworx-web --org personal 2>/dev/null || echo "manualworx-web already exists"

# Worker
flyctl apps create manualworx-worker --org personal 2>/dev/null || echo "manualworx-worker already exists"

# DocGen
flyctl apps create manualworx-docgen --org personal 2>/dev/null || echo "manualworx-docgen already exists"

echo ""
echo "--- Provisioning Postgres ---"
flyctl postgres create \
    --name manualworx-db \
    --region ord \
    --vm-size shared-cpu-1x \
    --initial-cluster-size 1 \
    --volume-size 10 \
    2>/dev/null || echo "manualworx-db already exists"

# Attach to API app
flyctl postgres attach manualworx-db --app manualworx-api 2>/dev/null || echo "Already attached"

echo ""
echo "--- Creating Upstash Redis ---"
flyctl redis create \
    --name manualworx-redis \
    --region ord \
    --plan free \
    2>/dev/null || echo "manualworx-redis already exists"

echo ""
echo "--- Creating Tigris storage bucket ---"
flyctl storage create \
    --name manualworx-storage \
    --app manualworx-api \
    2>/dev/null || echo "Storage already exists"

echo ""
echo "--- Setting secrets ---"
echo "You'll need to set these secrets manually:"
echo ""
echo "  flyctl secrets set -a manualworx-api \\"
echo "    ANTHROPIC_API_KEY=sk-ant-... \\"
echo "    STRIPE_SECRET_KEY=sk_... \\"
echo "    STRIPE_WEBHOOK_SECRET=whsec_... \\"
echo "    SECRET_KEY=\$(openssl rand -base64 32) \\"
echo "    CORS_ORIGINS=https://manualworx-web.fly.dev"
echo ""
echo "  flyctl secrets set -a manualworx-web \\"
echo "    NEXT_PUBLIC_API_URL=https://manualworx-api.fly.dev \\"
echo "    NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_..."
echo ""
echo "  flyctl secrets set -a manualworx-worker \\"
echo "    DATABASE_URL=\$DATABASE_URL \\"
echo "    REDIS_URL=\$REDIS_URL"
echo ""
echo "=== Setup complete! ==="
echo "Next: run ./scripts/run-migrations.sh then deploy with make deploy"
