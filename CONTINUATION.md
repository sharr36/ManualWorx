# ManualWorx — Session Continuation Notes

## Current Phase: Phase 2 — Advanced Retrieval + Page Classification

### Plan File
`/root/.claude/plans/cozy-exploring-pancake.md`

### Branch
`claude/manual-intelligence-platform-Q2RAK`

### Phase 2 Batches

| Batch | Description | Status |
|-------|-------------|--------|
| 1 | Streaming query responses via SSE | In Progress |
| 2 | AI page classification with Claude vision | Pending |
| 3 | Hybrid retrieval + re-ranking | Pending |
| 4 | Ingestion progress SSE + page image proxy | Pending |
| 5 | Query history + UI polish | Pending |

### Batch 1 Progress (Streaming Query Responses)

**Completed:**
- `backend/app/services/ai_service.py` — Added `generate_response_stream()` (SSE token streaming via Anthropic streaming API) and `rerank_passages()` (Claude-based re-ranking)

**Remaining in Batch 1:**
- `backend/app/services/query_service.py` — Add `create_query_stream()` async generator
- `backend/app/routers/query.py` — Add `POST /api/query/stream` SSE endpoint with `StreamingResponse`
- `frontend/src/lib/api-client.ts` — Add `stream()` method for SSE consumption
- `frontend/src/app/(dashboard)/query/page.tsx` — Switch to streaming with `ReadableStream`

### Batch 2 Details (AI Page Classification)

**Files to modify:**
- `worker/app/pipeline/page_classifier.py` — Full implementation using Claude vision
- `worker/app/tasks/classify_pages.py` — Full implementation: fetch images, classify, update DB + Qdrant
- `worker/app/tasks/ingest_manual.py` — Enqueue `classify_pages` after ingestion
- `worker/app/config.py` — Add `CLASSIFICATION_MODEL`

### Batch 3 Details (Hybrid Retrieval + Re-ranking)

**Files to modify:**
- `backend/app/services/retrieval_service.py` — Add keyword extraction, score boosting, re-ranking pipeline
- `backend/app/services/ai_service.py` — `rerank_passages()` already added in Batch 1
- `backend/app/config.py` — Add `RERANK_ENABLED`, `RERANK_TOP_K`, `RERANK_MODEL`
- `backend/app/services/query_service.py` — Use `retrieve_with_rerank()` when config enabled

### Batch 4 Details (Ingestion Progress SSE + Page Image Proxy)

**Files to modify:**
- `worker/app/tasks/ingest_manual.py` — Publish progress to Redis pub/sub
- `backend/app/routers/manuals.py` — Add `GET /api/manuals/{id}/progress` SSE endpoint + `GET /api/manuals/{id}/pages/{page_number}/image` proxy
- `frontend/src/app/(dashboard)/manuals/[id]/page.tsx` — Subscribe to progress SSE, show page images

### Batch 5 Details (Query History + UI Polish)

**Files to modify:**
- `frontend/src/app/(dashboard)/query/page.tsx` — Add query history sidebar
- `frontend/src/components/query/source-citation.tsx` — Add page image thumbnails
- `frontend/src/components/query/chat-message.tsx` — Markdown rendering, copy button
- `frontend/src/app/(dashboard)/manuals/[id]/page.tsx` — Page image display in Pages tab

### Key Architecture Notes

- **Backend**: FastAPI, asyncpg, Pydantic v2, PostgreSQL with RLS, Redis for queues/cache
- **Worker**: arq (async Redis queue), PyMuPDF for PDF processing, Together.ai for embeddings, Qdrant for vectors
- **Frontend**: Next.js 15, React 19, Tailwind CSS 4, shadcn/ui
- **AI**: Anthropic Claude (claude-sonnet-4-5-20250929 for queries, claude-haiku-4-5-20251001 for re-ranking/classification)
- **Storage**: Tigris (S3-compatible via Fly.io)
- **Auth**: Custom Lucia-style session auth with argon2 + SHA-256

### Previous Phases Completed
- **Phase 0** (11 batches): Foundation — auth, billing, multi-tenancy, all provider stubs, DB migrations, frontend scaffold
- **Phase 1** (5 batches): PDF ingestion + basic query — worker pipeline, backend services/routers, frontend manuals + query pages
