# ManualWorx — Session Continuation Notes

## Current Status: Phase 10 Complete — All Phases Done

### Branch
`claude/manual-intelligence-platform-Q2RAK`

### Phase Completion Summary

**Phase 0** — Foundation: auth, billing, multi-tenancy, DB migrations, frontend scaffold
**Phase 1** — PDF ingestion + basic query: worker pipeline, services, manuals + query pages
**Phase 2** — SSE streaming, Claude vision classification, hybrid retrieval + re-ranking, ingestion progress, UI polish
**Phase 3** — Per-claim confidence scoring, contradiction detection, refinement suggestions
**Phase 4** — Document generation (PDF/DOCX) from query responses, templates, frontend documents page
**Phase 5** — Interactive schematic viewer: AI diagram annotation via Claude Vision, pan/zoom canvas with SVG overlays, component hotspots, operating state visualization, layer filtering, diagram comparison
**Phase 6** — Inference engine: coverage analysis, gap detection, component inference, text analysis, aggregate analysis, document templates for system_analysis and gap_report
**Phase 7** — Advanced query modes: multi-turn conversation, diagram-aware queries, auto mode detection, procedure + troubleshoot + diagram modes
**Phase 8** — Teaching mode: explain, assist, quiz generation, learning paths, progress tracking, system familiarity
**Phase 9** — Polish + optimization: structured logging, error handling, toast system, API client hardening, security headers, performance indexes, accessibility, Docker polish
**Phase 10** — Launch preparation (details below)

### Phase 10: What Was Done

**Environment Validation + Startup Checks**
- Added `@model_validator` to Settings class warning on missing critical config (ANTHROPIC_API_KEY, STRIPE_SECRET_KEY, insecure SECRET_KEY)
- Added `LOG_LEVEL` field to Settings
- Bumped API version to 1.0.0

**Password Validation**
- Added `@field_validator("password")` to `SignupRequest`: min 8 chars, uppercase, lowercase, digit required

**CSRF Protection**
- Created `backend/app/middleware/csrf.py` — double-submit cookie pattern
- On safe methods: sets `csrf_token` cookie (JS-readable)
- On mutating methods: validates `X-CSRF-Token` header matches cookie
- Exempts webhooks, health checks, docs endpoints
- Frontend API client reads `csrf_token` cookie and sends it as `X-CSRF-Token` on all POST/PUT/PATCH/DELETE
- Added `X-CSRF-Token` to CORS allowed headers

**Content Security Policy**
- Added CSP header to SecurityHeadersMiddleware: restricts script/style/img/connect/frame sources
- Allows Stripe.js (`js.stripe.com`, `api.stripe.com`)

**Dockerfile Hardening**
- Added non-root `appuser` to backend, worker, and docgen Dockerfiles
- All three services now run as unprivileged user

**Error Pages**
- Created `frontend/src/app/not-found.tsx` — branded 404 page with dashboard/home links
- Created `frontend/src/app/error.tsx` — catch-all error page with "Try Again" button
- Created `frontend/src/app/(dashboard)/loading.tsx` — skeleton loader for dashboard routes

**SEO + Meta Tags**
- Added OpenGraph tags (title, description, type, siteName)
- Added Twitter Card meta (summary_large_image)
- Added `metadataBase` for canonical URL resolution
- Added favicon reference and theme-color meta tag (#059669 emerald-600)

**CI Pipeline**
- Added `checks` job (lint + type check) to GitHub Actions workflow
- All deploy jobs now `needs: [checks]` — deploy blocked on lint/type errors
- Uses Node.js 22, runs `next lint` and `tsc --noEmit`

**Fly.io Production Config + Self-Hosted Qdrant**
- Changed backend `min_machines_running` from 0 to 1 (eliminates cold starts)
- Added `qdrant/fly.toml` for self-hosted Qdrant on Fly.io (persistent volume, health checks, always-on)
- Updated `scripts/setup-fly.sh` to create Qdrant app, volume, and set QDRANT_URL on API/worker
- Added Qdrant deploy job to CI pipeline

**Admin Analytics**
- Created `backend/app/routers/admin.py` with `GET /api/admin/stats` endpoint (owner-only)
- Returns: total_manuals, total_pages, queries_30d, total_documents, active_users_7d, total_users
- Added stats cards to admin page frontend: manuals, queries, documents, team metrics

### Key Architecture Notes

- **Backend**: FastAPI, asyncpg, Pydantic v2, PostgreSQL with RLS, Redis for queues/cache
- **Worker**: arq (async Redis queue), PyMuPDF for PDF processing, Together.ai for embeddings, Qdrant for vectors
- **Frontend**: Next.js 15, React 19, Tailwind CSS 4, shadcn/ui, sonner (toast)
- **AI**: Anthropic Claude (claude-sonnet-4-5-20250929 for queries, claude-haiku-4-5-20251001 for re-ranking/classification)
- **Storage**: Tigris (S3-compatible via Fly.io)
- **Auth**: Custom Lucia-style session auth with argon2 + SHA-256, CSRF double-submit cookie
- **Version**: 1.0.0
