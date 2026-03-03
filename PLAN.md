# ManualWorx — Full Scaffold + Phase 0 Implementation Plan

## Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| Product name | ManualWorx | Matches repo name |
| Repo layout | Monorepo: `/frontend`, `/backend`, `/worker`, `/docgen` | Shared types, simpler CI, one repo to rule them all |
| Python version | 3.12 | Best async perf, modern type hints, pattern matching |
| Node version | 22 | Latest stable, native fetch, improved ESM |
| Frontend | Next.js 15 + Tailwind CSS + shadcn/ui | Fast iteration, excellent component library, clean aesthetic that maps well to the mountain/professional brand |
| Backend | FastAPI + asyncpg + Pydantic v2 | Best Python async framework, shared codebase with ML/doc pipeline |
| Auth | Lucia (via `lucia-auth`) on the backend, custom Next.js auth pages | Better control over multi-tenant flows, cleaner RBAC model, no magic. Sessions stored in Postgres. |
| OCR | Abstracted `OCRProvider` interface — PyMuPDF (default) + Azure DI (flag-enabled) | Works locally with no API key, Azure DI drops in when ready |
| Embeddings | Abstracted `EmbeddingProvider` — Together.ai (default) + self-hosted (flag-enabled) | Swap without re-architecting |
| Vector DB | Qdrant (self-hosted on Fly) | Single platform, no external dependency |
| Object storage | Tigris (Fly-native S3) | Zero egress cost within Fly |
| Cache/queue | Redis (Upstash via Fly) | Job queue (RQ or arq) + response caching |
| Payments | Stripe Billing + Checkout + Webhooks | Subscriptions + one-time manual processing fees |
| Deployment | Fly.io — all services | One platform, one CLI, GPU available |

---

## Repository Structure

```
ManualWorx/
├── frontend/                        # Next.js 15 app
│   ├── src/
│   │   ├── app/                     # App Router pages
│   │   │   ├── (auth)/              # Login, signup, forgot-password
│   │   │   ├── (dashboard)/         # Authenticated routes
│   │   │   │   ├── manuals/         # Manual library management
│   │   │   │   ├── query/           # Chat/query interface
│   │   │   │   ├── viewer/          # Schematic viewer
│   │   │   │   ├── teach/           # Teaching mode
│   │   │   │   ├── documents/       # Generated documents
│   │   │   │   ├── settings/        # Tenant/user settings
│   │   │   │   ├── billing/         # Subscription management
│   │   │   │   └── admin/           # Shop admin (users, analytics)
│   │   │   ├── api/                 # Next.js API routes (auth, Stripe webhooks)
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx             # Landing/marketing page
│   │   ├── components/
│   │   │   ├── ui/                  # shadcn/ui components
│   │   │   ├── auth/                # Auth forms
│   │   │   ├── manuals/             # Manual upload, library list
│   │   │   ├── query/               # Chat interface, response display
│   │   │   ├── viewer/              # Schematic viewer canvas + overlays
│   │   │   ├── teach/               # Teaching mode UI
│   │   │   ├── documents/           # Doc generation UI
│   │   │   └── layout/              # Sidebar, header, navigation
│   │   ├── lib/
│   │   │   ├── api-client.ts        # Typed FastAPI client
│   │   │   ├── auth.ts              # Lucia auth helpers
│   │   │   ├── stripe.ts            # Stripe client-side helpers
│   │   │   └── utils.ts
│   │   └── types/
│   │       └── index.ts             # Shared TypeScript types
│   ├── public/
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
│
├── backend/                         # FastAPI API server
│   ├── app/
│   │   ├── main.py                  # FastAPI app, lifespan, middleware
│   │   ├── config.py                # Settings from env vars (Pydantic BaseSettings)
│   │   ├── database.py              # asyncpg pool, RLS helper
│   │   ├── models/                  # Pydantic models (request/response)
│   │   │   ├── __init__.py
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   ├── manual.py
│   │   │   ├── query.py
│   │   │   ├── document.py
│   │   │   ├── teaching.py
│   │   │   ├── viewer.py
│   │   │   └── billing.py
│   │   ├── routers/                 # API route handlers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # Auth endpoints
│   │   │   ├── tenants.py           # Tenant management
│   │   │   ├── users.py             # User management (RBAC)
│   │   │   ├── manuals.py           # Manual upload + management
│   │   │   ├── query.py             # Main query/chat endpoint
│   │   │   ├── documents.py         # Doc generation
│   │   │   ├── teaching.py          # Teaching mode endpoints
│   │   │   ├── viewer.py            # Schematic viewer endpoints
│   │   │   ├── analyze.py           # Inference engine endpoints
│   │   │   ├── billing.py           # Billing/Stripe endpoints
│   │   │   └── health.py            # Health check
│   │   ├── services/                # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── tenant_service.py
│   │   │   ├── manual_service.py
│   │   │   ├── query_service.py
│   │   │   ├── retrieval_service.py # Vector search + reranking
│   │   │   ├── ai_service.py        # Claude API interactions
│   │   │   ├── document_service.py
│   │   │   ├── teaching_service.py
│   │   │   ├── viewer_service.py
│   │   │   ├── inference_service.py
│   │   │   ├── confidence_service.py
│   │   │   └── billing_service.py
│   │   ├── providers/               # Abstracted external services
│   │   │   ├── __init__.py
│   │   │   ├── ocr/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py          # OCRProvider abstract class
│   │   │   │   ├── pymupdf.py       # PyMuPDF implementation
│   │   │   │   └── azure_di.py      # Azure DI implementation
│   │   │   ├── embedding/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py          # EmbeddingProvider abstract class
│   │   │   │   ├── together.py      # Together.ai implementation
│   │   │   │   └── self_hosted.py   # Self-hosted GPU implementation
│   │   │   ├── storage/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py          # StorageProvider abstract class
│   │   │   │   └── tigris.py        # Tigris/S3 implementation
│   │   │   └── vector/
│   │   │       ├── __init__.py
│   │   │       ├── base.py          # VectorProvider abstract class
│   │   │       └── qdrant.py        # Qdrant implementation
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── tenant.py            # Tenant context + RLS middleware
│   │   │   ├── auth.py              # Auth middleware (session validation)
│   │   │   └── rate_limit.py        # Query usage tracking
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── security.py          # Password hashing, token utils
│   ├── migrations/                  # SQL migration files
│   │   ├── 001_tenants_and_users.sql
│   │   ├── 002_manuals_and_pages.sql
│   │   ├── 003_queries_and_documents.sql
│   │   ├── 004_teaching_and_learning.sql
│   │   ├── 005_inference_and_confidence.sql
│   │   ├── 006_viewer_and_schematics.sql
│   │   ├── 007_billing_and_usage.sql
│   │   └── 008_rls_policies.sql
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── fly.toml
│
├── worker/                          # Ingestion pipeline worker
│   ├── app/
│   │   ├── main.py                  # Worker entry point (arq)
│   │   ├── config.py                # Shared config
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── ingest_manual.py     # Full ingestion pipeline
│   │   │   ├── process_page.py      # Single page processing
│   │   │   ├── generate_embeddings.py
│   │   │   ├── classify_pages.py
│   │   │   ├── annotate_diagram.py  # AI diagram annotation
│   │   │   └── generate_learning_path.py
│   │   └── pipeline/
│   │       ├── __init__.py
│   │       ├── pdf_splitter.py
│   │       ├── ocr_processor.py     # Uses providers/ocr
│   │       ├── page_classifier.py
│   │       ├── chunker.py
│   │       └── embedder.py          # Uses providers/embedding
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── fly.toml
│
├── docgen/                          # Document generation service
│   ├── app/
│   │   ├── main.py                  # FastAPI micro-service
│   │   ├── templates/               # Jinja2 templates
│   │   │   ├── troubleshooting_guide.html
│   │   │   ├── service_procedure.html
│   │   │   ├── parts_reference.html
│   │   │   ├── quick_reference.html
│   │   │   ├── training_lesson.html
│   │   │   ├── quiz_assessment.html
│   │   │   ├── progress_report.html
│   │   │   ├── system_analysis.html
│   │   │   └── gap_report.html
│   │   ├── generators/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_generator.py     # weasyprint
│   │   │   └── docx_generator.py    # python-docx
│   │   └── styles/
│   │       └── manualworx.css       # Brand-consistent PDF styling
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── fly.toml
│
├── shared/                          # Shared Python code (installed as package)
│   ├── manualworx_shared/
│   │   ├── __init__.py
│   │   ├── models.py                # Shared Pydantic models
│   │   ├── config.py                # Shared config base
│   │   └── constants.py             # Enums, page classifications, etc.
│   └── pyproject.toml
│
├── assets/
│   └── symbols/                     # ISO 1219 / IEC 60617 SVG symbol library
│       ├── hydraulic/               # Pumps, valves, cylinders, etc.
│       └── electrical/              # Switches, relays, solenoids, etc.
│
├── scripts/
│   ├── setup-fly.sh                 # Fly.io project creation script
│   ├── run-migrations.sh            # Apply SQL migrations
│   └── seed-dev.sh                  # Seed dev data
│
├── .github/
│   └── workflows/
│       └── deploy.yml               # CI/CD to Fly.io
│
├── .gitignore
├── .env.example                     # All environment variables
├── docker-compose.yml               # Local dev (Postgres, Redis, Qdrant)
├── Makefile                         # Common commands
└── README.md                        # Setup instructions
```

---

## Implementation Steps (This Session)

### Step 1: Root Configuration
- `.gitignore` (Python + Node + IDE + env files)
- `.env.example` with all env vars from the spec
- `Makefile` with common dev commands
- `docker-compose.yml` for local dev fallback (Postgres 16, Redis 7, Qdrant)
- `README.md` with setup instructions

### Step 2: Shared Python Package
- `shared/manualworx_shared/` — shared constants (page classifications, roles, plan tiers), Pydantic base models, config utilities

### Step 3: Backend — FastAPI API Server (Phase 0 focus)
- **Project setup**: `pyproject.toml` with all dependencies, `Dockerfile`, `fly.toml`
- **Config**: Pydantic `BaseSettings` loading all env vars
- **Database**: asyncpg pool with RLS context setter, migration runner
- **Migrations**: Full schema — all tables from the spec (tenants, users, manuals, pages, chunks, queries, documents, teaching tables, inference tables, viewer tables, billing tables) + RLS policies
- **Auth**: Lucia-style session auth — signup, login, logout, session validation, password hashing (argon2)
- **Tenant middleware**: Sets `app.current_tenant_id` on every request for RLS
- **RBAC middleware**: Checks user role against required permission for each endpoint
- **Routers**: All endpoint stubs defined with proper Pydantic models (implemented for Phase 0: auth, tenants, users, billing, health; stubbed for later phases: manuals, query, documents, teaching, viewer, analyze)
- **Services**: Auth service, tenant service, billing service (Stripe integration) fully implemented; others stubbed
- **Providers**: Abstract base classes for OCR, embedding, storage, vector — with PyMuPDF and Tigris/S3 implementations

### Step 4: Frontend — Next.js 15 App
- **Project setup**: `package.json`, `next.config.ts`, `tailwind.config.ts`, `tsconfig.json`, `Dockerfile`
- **shadcn/ui init**: Button, Card, Input, Dialog, Dropdown, Sidebar, etc.
- **Layout**: App shell with sidebar navigation, tenant context, auth state
- **Auth pages**: Login, signup, forgot password forms
- **Dashboard shell**: Landing dashboard with placeholder cards for each feature
- **Settings page**: Tenant settings, user profile
- **Billing page**: Stripe Checkout integration, plan display, usage meters
- **Manual library page**: Upload UI (placeholder), list view
- **Query page**: Chat interface shell (placeholder for AI integration)
- **Typed API client**: Fetch wrapper matching the FastAPI endpoints

### Step 5: Worker Service
- **Project setup**: `pyproject.toml`, `Dockerfile`, `fly.toml`
- **arq worker**: Task runner with Redis queue
- **Pipeline stubs**: PDF splitter, OCR processor, classifier, chunker, embedder — all with abstracted providers
- **Ingestion task**: Full orchestration function (stubbed internals)

### Step 6: Doc Generation Service
- **Project setup**: `pyproject.toml`, `Dockerfile`, `fly.toml`
- **FastAPI micro-service**: `/generate` endpoint
- **Jinja2 templates**: All 9 document types (HTML templates, basic structure)
- **PDF/Word generators**: weasyprint + python-docx wrappers
- **Brand CSS**: ManualWorx styling for generated PDFs

### Step 7: Fly.io Configuration
- `fly.toml` for each service (frontend, backend, worker, docgen)
- `scripts/setup-fly.sh`: Creates Fly apps, Postgres, Redis, Tigris bucket, Qdrant machine
- GitHub Actions deploy workflow

### Step 8: Stripe Integration (Phase 0 implementation)
- Plan/price configuration
- Checkout session creation
- Webhook handler (subscription lifecycle events)
- Customer Portal redirect
- Manual processing fee payment intent
- Usage tracking in Redis

---

## What Gets FULLY Implemented vs. STUBBED

### Fully Implemented (Phase 0)
- All database migrations (complete schema for all phases)
- Auth flow (signup, login, logout, sessions)
- Multi-tenancy with RLS
- RBAC (owner/manager/technician)
- Stripe integration (subscriptions, processing fees, webhooks)
- Usage tracking (query metering)
- Tenant/user management API + UI
- Health checks, config, middleware
- Fly.io deployment configs
- CI/CD pipeline

### Stubbed with Types + Interfaces (Phases 1-9)
- Manual upload endpoint (accepts file, returns 501 "coming soon")
- Query endpoint (accepts question, returns 501)
- All teaching, viewer, inference, docgen endpoints (defined but return 501)
- Provider implementations (abstract classes + PyMuPDF/Tigris concrete classes exist but ingestion pipeline isn't wired)
- Worker tasks (function signatures + docstrings, no implementation)
- Frontend pages for manuals, query, viewer, teach, documents (UI shells with "Coming Soon" state)

This gives you a **fully functional auth + billing + tenancy platform** on day one, with the entire codebase architecture ready for each subsequent phase to fill in.
