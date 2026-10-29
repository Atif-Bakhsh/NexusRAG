# Local runbook

Run commands from the repository root. Docker Compose is the simplest complete workflow.
The development workflow runs Python on the host with only databases in Docker. Do not run
both API/UI variants on the same ports. A 16 GB machine is recommended.

## Fresh installation and free setup

Install Git, Docker Desktop (or Docker Engine with Compose), Python 3.12, and uv 0.12.9.
No GPU or Astronomy Shop installation is required.

```sh
git clone https://github.com/Atif-Bakhsh/NexusRAG.git
cd NexusRAG
cp .env.example .env
# Leave OPENAI_API_KEY empty and DISABLE_PAID_API=true.
uv sync --frozen --extra dev
docker info
DISABLE_PAID_API=true docker compose up -d --build --wait
docker compose exec -T api nexusrag validate
docker compose exec -T api nexusrag download-model
docker compose exec -T -e DISABLE_PAID_API=true api nexusrag preflight
docker compose exec -T -e DISABLE_PAID_API=true api nexusrag ingest --fixture-graph
docker compose exec -T -e DISABLE_PAID_API=true api nexusrag preflight --require-ready
```

`download-model` downloads pinned BGE weights and the o200k_base tokenizer. It is free.
A fresh preflight may warn that no corpus is ingested. --require-ready makes that an error.
Preflight never downloads weights or contacts OpenAI; missing local weights are a failure.

Short equivalents after cloning: `make setup`, `make up`, `make download-model`,
`make ingest-fixture`, `make preflight`. Make's up, ask, fixture and evaluation commands keep
paid calls disabled. The persistent model cache inside Docker is separate from the host cache.

## Queries and inspectable evidence

```sh
docker compose exec -T -e DISABLE_PAID_API=true api nexusrag ask \
  'What is Checkout responsible for?' --mode vector --retrieval-only
docker compose exec -T -e DISABLE_PAID_API=true api nexusrag ask \
  'How does Checkout reach Quote through Shipping?' --mode graph_vector --retrieval-only
make ask MODE=vector QUESTION='What is Checkout responsible for?'
make ask
```

JSON contains evidence, paths, a query ID and trace. Retrieval-only returns no generated answer,
except a deterministic clarification where applicable. Use the query ID in the UI's Evidence
and execution view to inspect the stored record without generating another answer.

Generation commands below are **paid**, and belong only to the later live experiment:

```sh
# Requires key and DISABLE_PAID_API=false; do not run during free verification.
docker compose exec -T api nexusrag ingest
docker compose exec -T api nexusrag ask 'What is Checkout responsible for?' --mode vector
docker compose exec -T api nexusrag ask 'How does Checkout reach Quote through Shipping?' --mode graph_vector
```

For recovery without extraction calls, reuse an export from the identical index:

```sh
docker compose exec -T -e DISABLE_PAID_API=true api nexusrag ingest \
  --fixture-graph --assertions artifacts/INDEX_VERSION/assertions.jsonl
# Omit --fixture-graph for an LLM graph export. Substitute the actual directory.
```

An intact ready version is a no-op. The fixture flag must match the artifact's graph identity.
Old pre-audit exports have historical IDs; preserve them rather than relabeling as a new index.

## API and Streamlit

Open [Streamlit](http://127.0.0.1:58501), [OpenAPI](http://127.0.0.1:58000/docs), or
[Neo4j Browser](http://127.0.0.1:57474).

```sh
curl --fail http://127.0.0.1:58000/health
curl --fail http://127.0.0.1:58000/ready
curl --fail http://127.0.0.1:58000/documents
# Substitute IDs from a CLI result:
curl --fail http://127.0.0.1:58000/chunks/CHUNK_ID
curl --fail http://127.0.0.1:58000/queries/QUERY_ID
curl --fail http://127.0.0.1:58000/queries/QUERY_ID/trace
```

For free evidence search, pass `generate=false` as a query parameter:

```sh
curl --fail-with-body 'http://127.0.0.1:58000/ask?generate=false' \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does Checkout reach Quote through Shipping?","mode":"graph_vector"}'
```

The response includes the same evidence, paths, query ID and trace as the retrieval-only CLI.
It records `generation_requested=false` and zero provider calls. A deterministic clarification
may still be returned for ambiguous phrasing.

Omitting the parameter preserves the API's existing answer-generation behavior. After
explicitly enabling the later live experiment:

```sh
curl --fail-with-body http://127.0.0.1:58000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is Checkout responsible for?","mode":"vector","document_filter":["checkout","services"]}'
```

The UI's Ask/Compare view defaults to free evidence search; Compare makes two independent
requests. Enable **Generate an answer (uses paid API)** to request answers when the server
reports generation configured. The Benchmark view also shows the committed development
diagnostic on a fresh clone.

## Host Python development

```sh
make setup
docker compose stop api ui
docker compose up -d --wait postgres neo4j
uv run --frozen --extra dev --env-file .env alembic upgrade head
uv run --frozen --extra dev --env-file .env nexusrag validate
uv run --frozen --extra dev --env-file .env nexusrag download-model
DISABLE_PAID_API=true uv run --frozen --extra dev --env-file .env nexusrag ingest --fixture-graph
DISABLE_PAID_API=true uv run --frozen --extra dev --env-file .env nexusrag preflight --require-ready
DISABLE_PAID_API=true uv run --frozen --extra dev --env-file .env uvicorn nexusrag.api.app:app --host 127.0.0.1 --port 58000
# Another terminal, same working directory:
uv run --frozen --extra dev --env-file .env streamlit run src/nexusrag/ui.py --server.address 127.0.0.1 --server.port 58501
```

After downloading, prefix host retrieval commands with HF_HUB_OFFLINE=1. For containers:
`docker compose exec -e HF_HUB_OFFLINE=1 -e DISABLE_PAID_API=true api nexusrag ask ... --retrieval-only`.

## Evaluation and scoring

```sh
docker compose exec -T -e DISABLE_PAID_API=true api nexusrag evaluate --split dev --allow-unreviewed
# Same free diagnostic:
make evaluate
# PAID, later, after human labels and LLM graph review:
docker compose exec -T api nexusrag evaluate --split test --generate --repeats 3
# Free scoring, only after completing the generated judgments.csv:
docker compose exec -T api nexusrag score results/runs/RUN_ID
```

Every run writes configuration.json, questions.jsonl, raw.jsonl, summary.json and judgments.csv.
Scoring adds human_scores.json. Retrieval-only runs cannot be scored as generated-answer quality.
See [FINAL-EXPERIMENT.md](FINAL-EXPERIMENT.md) for gates and interpretation.

## All free verification

```sh
make validate
make lint
make typecheck
make test
make integration
# Host model cache must have been downloaded separately:
make model-test
make build
DISABLE_PAID_API=true docker compose up -d --wait
make ingest-fixture
make smoke
git diff --check
```

Expanded commands:

```sh
uv run --frozen --extra dev ruff check src tests scripts migrations
uv run --frozen --extra dev ruff format --check src tests scripts migrations
uv run --frozen --extra dev mypy src
DISABLE_PAID_API=true uv run --frozen --extra dev --env-file .env pytest -q
DISABLE_PAID_API=true RUN_INTEGRATION=1 uv run --frozen --extra dev --env-file .env pytest -q tests/test_integration.py
DISABLE_PAID_API=true RUN_MODEL=1 HF_HUB_OFFLINE=1 uv run --frozen --extra dev --env-file .env pytest -q -m model
uv run --frozen --extra dev python scripts/smoke.py
```

Unit tests block construction of a live provider client. Integration tests write only unique
test corpus namespaces and clean up their own rows/nodes. Smoke saves real free query records.

## Database and graph inspection

```sh
docker compose exec postgres psql -U nexusrag -d nexusrag
```

Inside psql:

```sql
SELECT extversion FROM pg_extension WHERE extname = 'vector';
SELECT * FROM alembic_version;
SELECT version, ready, configuration->>'graph_source' AS graph_source FROM corpora ORDER BY created_at DESC;
SELECT corpus_version, count(*) FROM chunks GROUP BY corpus_version;
SELECT query_id, created_at FROM query_runs ORDER BY created_at DESC LIMIT 5;
\q
```

Migrations: `uv run --env-file .env alembic current`,
`uv run --env-file .env alembic heads`, `uv run --env-file .env alembic upgrade head`.

Neo4j Browser connects to bolt://127.0.0.1:57687 using neo4j and the configured local password.
For a terminal, use `docker compose exec neo4j cypher-shell -u neo4j` and enter the password
at the prompt. Do not paste passwords into command history. Read-only inspection:

```cypher
MATCH (c:Corpus) RETURN c.version, c.assertion_count;
MATCH (n:Entity) RETURN n.corpus_version, n.entity_type, count(*);
MATCH (a:Entity)-[r]->(b:Entity)
RETURN a.corpus_version, a.entity_id, type(r), b.entity_id LIMIT 40;
```

## Stop, restart and rebuild

```sh
docker compose stop
docker compose start
docker compose down
# Rebuild/recreate after code/config changes or a repository folder move:
DISABLE_PAID_API=true docker compose up -d --build --wait
```

`down` preserves named database/model volumes and host artifacts. After a folder rename,
run `uv sync --frozen --extra dev --reinstall` to refresh all Python entrypoints and recreate api/ui bind mounts.

A **destructive complete database/model reset** removes corpora and query history. Back up any
live experiment first. This is a documented recovery procedure, not part of ordinary tests:

```sh
# Choose a new, unused backup path; retain the spend ledger.
cp -R artifacts ../nexusrag-artifacts-backup
cp -R results ../nexusrag-results-backup
docker compose down --volumes
DISABLE_PAID_API=true docker compose up -d --build --wait
docker compose exec -T api nexusrag download-model
docker compose exec -T -e DISABLE_PAID_API=true api nexusrag ingest --fixture-graph
docker compose exec -T api nexusrag preflight --require-ready
```

Keep artifacts/spend.sqlite in place; it survives this reset. Matching exports/caches can rebuild
the graph without new extraction. Never delete the ledger to bypass the application budget.
