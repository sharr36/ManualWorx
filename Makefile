.PHONY: dev-backend dev-frontend dev-worker dev-docgen dev-infra migrate seed test lint help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Infrastructure ---
dev-infra: ## Start local Postgres, Redis, Qdrant
	docker compose up -d

dev-infra-down: ## Stop local infrastructure
	docker compose down

# --- Backend ---
dev-backend: ## Run FastAPI backend (hot reload)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# --- Frontend ---
dev-frontend: ## Run Next.js frontend (hot reload)
	cd frontend && npm run dev

# --- Worker ---
dev-worker: ## Run ingestion worker
	cd worker && python -m app.main

# --- Document Generation ---
dev-docgen: ## Run doc generation service
	cd docgen && uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# --- Database ---
migrate: ## Run database migrations
	cd backend && python -c "import asyncio; from app.database import create_pool, run_migrations; asyncio.run(run_migrations(asyncio.run(create_pool())))"

seed: ## Seed development data
	bash scripts/seed-dev.sh

# --- Testing ---
test: ## Run all tests
	cd backend && python -m pytest
	cd frontend && npm test

test-backend: ## Run backend tests only
	cd backend && python -m pytest

# --- Linting ---
lint: ## Lint all code
	cd backend && ruff check .
	cd frontend && npx next lint

lint-fix: ## Fix lint issues
	cd backend && ruff check --fix .

# --- Build ---
build-frontend: ## Build frontend for production
	cd frontend && npm run build

build-docker: ## Build all Docker images
	docker build -t manualworx-api ./backend
	docker build -t manualworx-web ./frontend
	docker build -t manualworx-worker ./worker
	docker build -t manualworx-docgen ./docgen

# --- Fly.io Deployment ---
deploy-api: ## Deploy backend to Fly.io
	cp -r shared backend/_shared
	cd backend && flyctl deploy; rm -rf _shared

deploy-web: ## Deploy frontend to Fly.io
	cd frontend && flyctl deploy

deploy-worker: ## Deploy worker to Fly.io
	cp -r shared worker/_shared
	cd worker && flyctl deploy; rm -rf _shared

deploy-docgen: ## Deploy docgen to Fly.io
	cp -r shared docgen/_shared
	cd docgen && flyctl deploy; rm -rf _shared

deploy-all: deploy-api deploy-web deploy-worker deploy-docgen ## Deploy all services
