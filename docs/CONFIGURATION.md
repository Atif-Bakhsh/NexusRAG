# Configuration reference

Copy `.env.example` to `.env`; never commit it. Settings are loaded from process environment,
then `.env`, then Python defaults. Constructor arguments override these in tests.
Use `uv run --env-file .env` for host commands so Hugging Face and tokenizer libraries receive
their environment too. Compose reads `.env` for interpolation; it only forwards variables
explicitly listed in `compose.yaml`.

All application variables are optional because local defaults exist. OPENAI_API_KEY becomes
required only for live extraction/generation, together with DISABLE_PAID_API=false.
No configuration variable itself makes a paid request.

## Application settings

Defaults below are Python defaults; keep these values for the controlled experiment.

| Variable | Default / safe development value | Purpose and paid-use relevance |
| --- | --- | --- |
| DATABASE_URL | `postgresql+psycopg://nexusrag:nexusrag-local-only@127.0.0.1:55433/nexusrag` | Authenticated host PostgreSQL connection; free |
| NEO4J_URI | `bolt://127.0.0.1:57687` | Host graph connection; free |
| NEO4J_USER | `neo4j` | Graph login; free |
| NEO4J_PASSWORD | `nexusrag-local-only` | Local graph password; free |
| OPENAI_API_KEY | Empty | Server-side provider credential; leave empty for free development |
| DISABLE_PAID_API | `true` | Blocks all paid calls, even with a key; set false only for the intentional live experiment |
| GENERATION_MODEL | `gpt-5.4-mini-2026-03-17` | Extraction and generation model; used only by paid operations |
| EMBEDDING_MODEL | `BAAI/bge-small-en-v1.5` | Local CPU embedding model; initial free download |
| EMBEDDING_REVISION | `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` | Immutable model revision; free |
| CORPUS_DIR | `corpus` | Fixed manifest and Markdown root; free |
| ARTIFACT_DIR | `artifacts` | Exports, extraction cache and persistent spend ledger |
| RESULTS_DIR | `results/runs` | Benchmark output directory; evaluation is free without --generate |
| API_BUDGET_USD | `50` | Application spending ceiling; positive and at most 50; lower if desired |
| INPUT_USD_PER_MILLION | `0.75` | Positive finite input-token price estimate; applies only to paid usage |
| OUTPUT_USD_PER_MILLION | `4.50` | Positive finite output-token price estimate; applies only to paid usage |
| CANDIDATE_K | `20` | Vector candidate cap, 1–20; free |
| CONTEXT_CHUNKS | `8` | Distinct final chunks, 1–8; affects live prompt size |
| CONTEXT_TOKENS | `3000` | Serialized evidence-token budget, 1–3000; affects live prompt size |
| MAX_OUTPUT_TOKENS | `1800` | Generation limit, 1–4000; extraction explicitly uses 4000 |
| PROMPT_VERSION | `grounded-v1` | Recorded answer prompt version; update when changing prompt behavior |
| EXTRACTION_PROMPT_VERSION | `ontology-v1` | Extraction/index version; changing it creates a new index/cache |
| CHUNKER_VERSION | `markdown-lines-v1` | Chunker/index version; update when changing boundaries |
| GRAPH_SOURCE | `llm` | Extraction identity; --fixture-graph explicitly changes it to mermaid_fixture |

Changing model names is not a substitute for implementing compatible dimensions/token limits.
This build supports the pinned BGE model and a 384-dimensional schema. Freeze retrieval and
generation settings before the held-out comparison.

Compose sets internal DATABASE_URL, NEO4J_URI and cache paths, and forwards NEO4J_PASSWORD,
OPENAI_API_KEY, DISABLE_PAID_API, GENERATION_MODEL, the two price rates and API_BUDGET_USD.
Other application settings use their defaults inside containers. To conduct an explicit
configuration experiment, use `docker compose exec -e NAME=value api ...` consistently for
ingestion and evaluation, or add an explicit Compose override. Editing a host-only variable in
.env does not silently change the container. Recreate api after changing forwarded settings.

## Compose, UI, libraries and test controls

| Variable | Required? / default | Purpose / safe value / paid usage |
| --- | --- | --- |
| POSTGRES_PASSWORD | Optional; nexusrag-local-only | Compose database and API authentication; free. Keep host DATABASE_URL consistent if changed |
| API_BASE_URL | Optional; http://127.0.0.1:58000 | Host Streamlit backend; Compose sets http://api:8000; UI Ask may generate paid calls only if server permits |
| HF_HOME | Optional library cache; example .cache/huggingface | Local model cache; Compose /app/.cache/huggingface; no API charge |
| HF_HUB_OFFLINE | Optional; unset | Set 1 after download to avoid Hugging Face network requests; unset for download-model |
| HF_TOKEN | Optional library setting; unset | Not needed for this public model; may increase free download limits; never commit a token |
| TIKTOKEN_CACHE_DIR | Optional library cache; example .cache/tiktoken | Generation-tokenizer cache, also used by retrieval context counting; Compose /app/.cache/tiktoken |
| RUN_INTEGRATION | Optional; unset | 1 enables database tests in isolated corpus namespaces; free |
| RUN_MODEL | Optional; unset | 1 enables cached real-model tests; free |
| UV_CACHE_DIR | Optional uv default | Dependency download cache; free; normally no need to override |
| UV_PROJECT_ENVIRONMENT | Docker-only /opt/venv | Installed virtual environment path; free |
| PYTHONUNBUFFERED | Docker-only 1 | Immediate process output; free |
| PATH | Inherited; Docker prepends /opt/venv/bin | Executable lookup; do not replace for application settings |
| POSTGRES_DB / POSTGRES_USER | Compose constants nexusrag | Database initialization; free |
| NEO4J_AUTH | Compose-derived neo4j/password | Neo4j initialization; never print expanded Compose config publicly |
| NEO4J_server_memory_heap_initial__size | Compose 256m | Heap initial allocation; free |
| NEO4J_server_memory_heap_max__size | Compose 512m | Heap ceiling; free |
| NEO4J_server_memory_pagecache_size | Compose 256m | Graph page cache; free |
| NEO4J_db_transaction_timeout | Compose 2s | Default graph transaction timeout; imports explicitly use 30s |

The price rates are the project's recorded planning estimates, not a fresh pricing guarantee.
Verify provider pricing before the live experiment. The $50 application ledger is not an
account-wide spending control. Unknown provider usage retains its reservation.
Do not publish `docker compose config`, `docker inspect` environment output, or local .env.
