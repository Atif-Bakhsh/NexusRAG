UV = uv run --frozen --extra dev --env-file .env
DC = docker compose
QUESTION ?= How does Checkout reach Quote through Shipping?
MODE ?= graph_vector

.PHONY: help setup up down validate download-model preflight ingest-fixture ask evaluate test integration model-test lint format typecheck build smoke
help:
	@echo "setup up down validate download-model preflight ingest-fixture ask evaluate test integration model-test lint format typecheck build smoke"
	@echo "ask/evaluate are retrieval-only. Live commands are in docs/FINAL-EXPERIMENT.md."
setup:
	@test -f .env || cp .env.example .env
	uv sync --frozen --extra dev
up:
	DISABLE_PAID_API=true $(DC) up -d --build --wait
down:
	$(DC) down
validate:
	$(UV) nexusrag validate
download-model:
	$(DC) exec -T api nexusrag download-model
preflight:
	$(DC) exec -T -e DISABLE_PAID_API=true api nexusrag preflight --require-ready
ingest-fixture:
	$(DC) exec -T -e DISABLE_PAID_API=true -e OPENAI_API_KEY= api nexusrag ingest --fixture-graph
ask:
	$(DC) exec -T -e DISABLE_PAID_API=true api nexusrag ask "$(QUESTION)" --mode "$(MODE)" --retrieval-only
evaluate:
	$(DC) exec -T -e DISABLE_PAID_API=true api nexusrag evaluate --split dev --allow-unreviewed
test:
	DISABLE_PAID_API=true $(UV) pytest -q
integration:
	DISABLE_PAID_API=true RUN_INTEGRATION=1 $(UV) pytest -q tests/test_integration.py
model-test:
	DISABLE_PAID_API=true RUN_MODEL=1 HF_HUB_OFFLINE=1 $(UV) pytest -q -m model
lint:
	$(UV) ruff check src tests scripts migrations
	$(UV) ruff format --check src tests scripts migrations
format:
	$(UV) ruff format src tests scripts migrations
typecheck:
	$(UV) mypy src
build:
	$(DC) build api ui
smoke:
	$(UV) python scripts/smoke.py
