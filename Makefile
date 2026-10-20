SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help dev backend-dev frontend-dev test backend-test frontend-test lint backend-lint frontend-lint eval offline-check

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{print $$1 " - " $$2}'

dev: backend-dev frontend-dev ## Start backend + frontend for local dev

backend-dev: ## Run FastAPI with reload on :8000
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend-dev: ## Run the Vite dev server (Agent B frontend if present)
	@if [ -d frontend ]; then $(MAKE) -C frontend dev; else echo "frontend/ not ready yet - Agent B owns it"; fi

test: backend-test frontend-test ## Run backend and frontend tests

backend-test: ## Backend: pytest
	cd backend && uv run pytest

frontend-test: ## Frontend: vitest (Agent B frontend if present)
	@if [ -d frontend ]; then $(MAKE) -C frontend test; else echo "frontend/ not ready yet"; fi

lint: backend-lint frontend-lint ## Lint backend and frontend

backend-lint: ## Backend: ruff + mypy strict
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests

frontend-lint: ## Frontend: eslint (Agent B frontend if present)
	@if [ -d frontend ]; then $(MAKE) -C frontend lint; else echo "frontend/ not ready yet"; fi

eval: ## Run the eval harness in --fake mode (Phase 2, Agent B harness)
	@if [ -f eval/run_eval.py ]; then cd backend && uv run python ../eval/run_eval.py --fake; else echo "eval/run_eval.py not ready yet - Phase 2"; fi

offline-check: ## Prove the pipeline runs with network blocked (Phase 3, Agent A)
	@bash scripts/offline_check.sh
