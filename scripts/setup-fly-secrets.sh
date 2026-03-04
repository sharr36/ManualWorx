#!/usr/bin/env bash
# Setup required Fly.io secrets for ManualWorx services.
# Usage: edit the values below, then run this script.

set -euo pipefail

APP_API="manualworx-api"
APP_WORKER="manualworx-worker"

echo "=== Setting secrets for $APP_API ==="

# ── Required ──────────────────────────────────────────────
# Database (Fly Postgres or external)
flyctl secrets set DATABASE_URL="postgres://..." --app "$APP_API"

# Session signing key (generate with: openssl rand -hex 32)
flyctl secrets set SECRET_KEY="$(openssl rand -hex 32)" --app "$APP_API"

# ── Recommended ───────────────────────────────────────────
# Redis (Upstash or Fly Redis)
# flyctl secrets set REDIS_URL="redis://..." --app "$APP_API"

# Qdrant (self-hosted on Fly or external)
# flyctl secrets set QDRANT_URL="http://manualworx-qdrant.internal:6333" --app "$APP_API"

# Anthropic (required for AI features)
# flyctl secrets set ANTHROPIC_API_KEY="sk-ant-..." --app "$APP_API"

# Stripe (required for billing)
# flyctl secrets set STRIPE_SECRET_KEY="sk_live_..." --app "$APP_API"
# flyctl secrets set STRIPE_WEBHOOK_SECRET="whsec_..." --app "$APP_API"

# Object storage (Tigris / S3-compatible)
# flyctl secrets set AWS_ENDPOINT_URL_S3="https://fly.storage.tigris.dev" --app "$APP_API"
# flyctl secrets set AWS_ACCESS_KEY_ID="..." --app "$APP_API"
# flyctl secrets set AWS_SECRET_ACCESS_KEY="..." --app "$APP_API"

# Embeddings
# flyctl secrets set TOGETHER_API_KEY="..." --app "$APP_API"

# CORS (comma-separated origins)
# flyctl secrets set CORS_ORIGINS="https://manualworx.com,https://www.manualworx.com" --app "$APP_API"

echo ""
echo "=== Setting secrets for $APP_WORKER ==="

# Worker needs the same database + service credentials
# flyctl secrets set DATABASE_URL="postgres://..." --app "$APP_WORKER"
# flyctl secrets set REDIS_URL="redis://..." --app "$APP_WORKER"
# flyctl secrets set QDRANT_URL="http://manualworx-qdrant.internal:6333" --app "$APP_WORKER"
# flyctl secrets set ANTHROPIC_API_KEY="sk-ant-..." --app "$APP_WORKER"
# flyctl secrets set TOGETHER_API_KEY="..." --app "$APP_WORKER"
# flyctl secrets set AWS_ENDPOINT_URL_S3="https://fly.storage.tigris.dev" --app "$APP_WORKER"
# flyctl secrets set AWS_ACCESS_KEY_ID="..." --app "$APP_WORKER"
# flyctl secrets set AWS_SECRET_ACCESS_KEY="..." --app "$APP_WORKER"

echo "Done. Verify with: flyctl secrets list --app $APP_API"
