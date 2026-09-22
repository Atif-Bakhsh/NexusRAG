# Initial implementation verification (historical)

Checked locally on 2026-09-20 with Python 3.12, the committed `uv.lock`, CPU BGE,
PostgreSQL 17/pgvector 0.8.0 and Neo4j Community 5.26.4.

| Check | Result |
|---|---|
| Ruff lint and formatting | Passed |
| mypy | Passed, 23 source modules |
| Full pytest suite with real model and local databases | 41 passed; no skips |
| Manifest and evaluation validation | 12 checksum-verified documents; 40 valid draft labels |
| Model limits and gold-span mapping | All chunks within 320 BGE tokens; all gold spans map |
| Re-ingestion and exact cosine fixtures | Passed |
| Four graph query families, reverse consumption, corpus isolation | Passed |
| Three-hop bound, simple paths, twenty-result truncation | Passed |
| Neo4j query timeout | Explicit failure verified |
| Complete source bundles and citation repair | Passed |
| API failure recording and secret-safe errors | Passed |
| Streamlit's three views | Passed using Streamlit AppTest |
| CPU-only application image build | Passed |
| Four-service Compose startup | Passed; all services healthy |
| Live API readiness and Streamlit health | HTTP 200 |
| Docker retrieval smoke | Three-hop Frontend → Checkout → Shipping → Quote; 8 source chunks; $0 API spend |
| Persisted smoke query via HTTP | HTTP 200; query `315ffa1c-b770-4828-a51e-67b92e427ac7` |
| Development retrieval diagnostic | 32 requests, no query failures, no paid calls |

The pytest run emitted two dependency deprecation warnings from Starlette's test client.
They do not affect the passing tests. Dependency versions are locked; no broad warning
suppression was added.

The paid OpenAI transport is mocked in tests, including malformed output and usage accounting.
No OPENAI_API_KEY was provided during implementation, so actual provider calls, extraction
quality and answer generation remain unverified. Draft labels are source-checked by the agent,
not independently human-reviewed. No held-out test query has been evaluated.

The diagnostic raw output and report are retained in `results/development-diagnostic/` and
`docs/report.md`. Tests intentionally distinguish valid citation pointers from claim entailment.

Docker Desktop delayed the initial host bind-mount startup, then started successfully without an application workaround. The running local UI is at http://127.0.0.1:58501.
