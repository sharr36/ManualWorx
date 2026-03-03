#!/usr/bin/env bash
set -euo pipefail

# ManualWorx — Run database migrations
# Usage: ./scripts/run-migrations.sh [local|fly]

MODE="${1:-local}"

if [ "$MODE" = "fly" ]; then
    echo "=== Running migrations on Fly Postgres ==="
    echo "Proxying Fly Postgres connection..."
    flyctl proxy 15432:5432 -a manualworx-db &
    PROXY_PID=$!
    sleep 2

    DATABASE_URL="postgresql://manualworx:$(flyctl secrets list -a manualworx-api | grep DATABASE_URL | awk '{print $2}')@localhost:15432/manualworx"

    for f in backend/migrations/*.sql; do
        echo "Applying: $(basename "$f")"
        psql "$DATABASE_URL" -f "$f" 2>/dev/null || echo "  (may already be applied)"
    done

    kill $PROXY_PID 2>/dev/null
else
    echo "=== Running migrations locally ==="
    DATABASE_URL="${DATABASE_URL:-postgresql://manualworx:password@localhost:5432/manualworx}"

    for f in backend/migrations/*.sql; do
        echo "Applying: $(basename "$f")"
        psql "$DATABASE_URL" -f "$f" 2>/dev/null || echo "  (may already be applied)"
    done
fi

echo "=== Migrations complete ==="
