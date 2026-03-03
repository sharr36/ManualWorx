# ManualWorx

AI-powered manual intelligence platform for heavy equipment mechanics. Part of the Fulcrum Systems product family.

## Architecture

```
ManualWorx/
├── shared/           # Shared Python package (constants, models, config)
├── backend/          # FastAPI API server (auth, billing, all endpoints)
│   ├── app/
│   │   ├── middleware/   # Auth, tenant context, rate limiting
│   │   ├── models/       # Pydantic request/response models
│   │   ├── routers/      # API endpoint handlers
│   │   ├── services/     # Business logic
│   │   └── providers/    # Abstracted OCR, embedding, storage, vector
│   └── migrations/       # PostgreSQL schema (8 migration files)
├── worker/           # arq background worker (PDF ingestion pipeline)
│   └── app/
│       ├── tasks/        # Job handlers (ingest, OCR, embed, classify)
│       └── pipeline/     # Processing components (splitter, chunker, etc.)
├── docgen/           # Document generation service (PDF/DOCX)
│   └── app/
│       ├── generators/   # WeasyPrint PDF + python-docx Word
│       └── templates/    # 9 Jinja2 document templates
├── frontend/         # Next.js 15 web application
│   └── src/
│       ├── app/          # App Router pages (auth, dashboard, features)
│       ├── components/   # UI components (shadcn/ui + domain-specific)
│       ├── lib/          # Utilities (auth, API client, Stripe)
│       └── types/        # TypeScript interfaces
├── scripts/          # Setup and deployment scripts
└── docker-compose.yml  # Local dev (Postgres, Redis, Qdrant)
```

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 22+
- Docker & Docker Compose

### Setup

```bash
# Start backing services
docker compose up -d

# Backend
cd backend
pip install -e ../shared -e ".[dev]"
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev

# Worker (separate terminal)
cd worker
pip install -e ../shared -e ".[dev]"
arq app.main.WorkerSettings
```

Or use the Makefile:

```bash
make dev-backend    # Start API server
make dev-frontend   # Start Next.js dev
make dev-worker     # Start background worker
make migrate        # Run database migrations
```

### Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `STRIPE_SECRET_KEY` | For billing | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | For billing | Stripe webhook signing secret |
| `AWS_ENDPOINT_URL_S3` | For storage | Tigris/S3 endpoint |
| `TOGETHER_API_KEY` | For embeddings | Together.ai API key |

## Deployment (Fly.io)

```bash
# One-time setup
./scripts/setup-fly.sh

# Set secrets
flyctl secrets set -a manualworx-api ANTHROPIC_API_KEY=sk-ant-...

# Deploy all services
make deploy
```

## Build Phases

| Phase | Weeks | Focus |
|-------|-------|-------|
| 0 | 1-2 | Foundation (auth, billing, multi-tenancy) ✅ |
| 1 | 3-5 | PDF ingestion + basic query |
| 2 | 5-7 | Advanced retrieval + page classification |
| 3 | 7-9 | Query refinement + confidence scoring |
| 4 | 9-11 | Document generation |
| 5 | 11-14 | Interactive schematic viewer |
| 6 | 14-17 | Inference engine |
| 7 | 17-19 | Advanced query + diagrams |
| 8 | 19-22 | Teaching mode |
| 9 | 22-24 | Polish + optimization |
| 10 | 24-26 | Launch preparation |

## Tech Stack

- **Backend**: FastAPI, asyncpg, Pydantic v2, argon2
- **Frontend**: Next.js 15, React 19, Tailwind CSS 4, shadcn/ui
- **Database**: PostgreSQL 16 with Row-Level Security
- **Queue**: arq (Redis-backed async job queue)
- **AI**: Anthropic Claude (reasoning + vision)
- **Embeddings**: Together.ai or self-hosted
- **Vector Store**: Qdrant (self-hosted on Fly)
- **Storage**: Tigris (Fly-native S3)
- **Billing**: Stripe (subscriptions + one-time processing fees)
- **Hosting**: Fly.io (4 services: API, Web, Worker, DocGen)

---

*ManualWorx — Leverage for the climb.*
