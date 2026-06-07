.DEFAULT_GOAL := help
.PHONY: help install lock db-up db-down data data-synthea data-nppes data-benefits \
        data-kb eval run test lint fmt clean

# Run python through the venv if present, else system.
PY ?= python

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime + dev deps and the spaCy model
	pip install -r requirements.txt
	pip install -e ".[dev]"
	$(PY) -m spacy download en_core_web_lg || $(PY) -m spacy download en_core_web_sm

lock: ## Recompile requirements.txt from requirements.in (pip-tools)
	pip-compile requirements.in -o requirements.txt

db-up: ## Start only the Postgres (pgvector) service
	docker compose up -d db

db-down: ## Stop the stack
	docker compose down

# ---- M0: data pipeline (idempotent; asserts row counts) ----
data: ## Run the full idempotent data pipeline (Synthea + NPPES + benefits + KB)
	$(PY) -m carenav.data.pipeline

data-synthea: ## Generate + load Synthea members/claims/accumulators
	$(PY) -m carenav.data.pipeline --only synthea

data-nppes: ## Load NPPES providers + plan_network
	$(PY) -m carenav.data.pipeline --only nppes

data-benefits: ## Load hand-authored benefit rules
	$(PY) -m carenav.data.pipeline --only benefits

data-kb: ## Build the KB corpus + embeddings (M1)
	$(PY) -m carenav.data.pipeline --only kb

# ---- later milestones ----
eval: ## Run the golden CUJ eval suite (M5)
	$(PY) -m eval.run

run: ## Serve the FastAPI turn endpoint (M2+)
	uvicorn carenav.api.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run the test suite
	$(PY) -m pytest -q

lint: ## Lint with ruff + mypy
	ruff check src eval tests
	mypy src/carenav

fmt: ## Auto-format / fix with ruff
	ruff check --fix src eval tests
	ruff format src eval tests

clean: ## Remove caches and generated artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache
