# NexusRAG

**Comparing Vector and Knowledge-Graph Retrieval for Architecture Documentation.**

The initial **retrieval-only development diagnostic** used 12 frozen documents and 16 questions.
Both modes found complete labeled evidence for 11/12 answerable questions; the other four ask
for clarification or unsupported conclusions. This is provisional: the graph was derived from
explicit Mermaid edges, labels await human review, and answer generation was not measured.
See [the measurement report](docs/report.md) for reproducible outputs and limitations.

NexusRAG is a local FastAPI + Streamlit application with exact pgvector search, CPU BGE
embeddings, evidence-backed Neo4j paths, structured OpenAI generation and an explicit paired
evaluation workflow. It reads Astronomy Shop documentation; it does not run Astronomy Shop.

## Run locally

Requirements: Docker Desktop/Compose, internet for the initial image/model downloads and an
OpenAI API key for LLM extraction/generation. Around 16 GB RAM is recommended. No hosting,
GPU, cloud services or Astronomy Shop installation is required.

```sh
cp .env.example .env
# Set OPENAI_API_KEY in .env for extraction/generation. Do not commit this file.
docker compose up -d --build
# Download the pinned BGE model and generation tokenizer into the persistent model cache.
docker compose exec api nexusrag download-model
# Paid extraction, guarded by the local $50 application budget:
docker compose exec api nexusrag ingest
```

Open [Streamlit](http://127.0.0.1:58501), [API docs](http://127.0.0.1:58000/docs), or
[Neo4j Browser](http://127.0.0.1:57474). Databases use the local credentials in `.env.example`;
all published ports bind to loopback. `/health` is liveness; `/ready` requires both databases
and a fully ingested corpus, and separately reports whether generation is configured.

For an **unpaid smoke test**, use the explicit fixture instead of paid ingestion:

```sh
docker compose exec api nexusrag ingest --fixture-graph
docker compose exec api nexusrag ask 'Trace Frontend → Checkout → Shipping → Quote.' \
  --mode graph_vector --retrieval-only
docker compose exec api nexusrag evaluate --split dev --allow-unreviewed
```

The fixture uses actual frozen source lines and actual BGE vectors. It is separately versioned
and labeled `mermaid_fixture`, never represented as LLM extraction. Generation still requires
a key. Streamlit reports missing configuration rather than fabricating answers. Re-ingest
without `--fixture-graph` when ready for the actual experiment; the newest ready version is used.

Stop with `docker compose down`; named database/model volumes and local artifacts remain.
Do not delete `artifacts/spend.sqlite` to reset spending. The budget is an application estimate,
not an invoice; failed calls with unknown usage retain their conservative reservations.

## Python development

Python 3.12 and uv 0.12.9; exact dependency versions and hashes are in `uv.lock`.
Linux PyTorch resolves from the CPU-only index. Other platforms use their native PyPI wheels.

```sh
uv sync --frozen --extra dev
docker compose up -d --wait postgres neo4j
uv run --env-file .env alembic upgrade head
uv run --env-file .env nexusrag validate
uv run --env-file .env nexusrag download-model
uv run --env-file .env nexusrag ingest --fixture-graph
uv run --env-file .env uvicorn nexusrag.api.app:app --host 127.0.0.1 --port 58000
# In another terminal:
uv run --env-file .env streamlit run src/nexusrag/ui.py --server.address 127.0.0.1 --server.port 58501
```

Do not run host API/UI and Compose API/UI simultaneously on the same ports. Set
`HF_HUB_OFFLINE=1` after model download for offline retrieval. Paid extraction and generation
always need provider access. Local `.env` configuration is loaded explicitly by `uv run`.

## Ingestion and querying

The fixed [manifest](corpus/manifest.json) records all sources, hashes, attribution and license.
The original Markdown is included, so ordinary ingestion does not fetch `main` or crawl links.
`scripts/freeze_corpus.py` reproduces exactly that allowlisted commit. There are 128 chunks
with exact line spans; Markdown page numbers are null. Every graph assertion contains exact
source quotes, model/prompt metadata and review status. Keep exported JSONL to rebuild Neo4j:

```sh
docker compose exec api nexusrag ingest --assertions artifacts/INDEX_VERSION/assertions.jsonl
# For a fixture export, add --fixture-graph to select that same index identity.
```

Re-ingestion is idempotent. Changed snapshot/model/chunker/aliases/extraction settings produce
a new index version. Failed versions stay unavailable. Do not edit a ready snapshot in place.

The UI has Ask/Compare, evidence/trace lookup and benchmark views. Compare sends two independent
requests. Answers link to pinned original source lines. Graph paths are plain text, with semantic
edge directions shown explicitly. Both modes use up to eight chunks and 3,000 evidence tokens.

| Endpoint | Purpose |
|---|---|
| `GET /health`, `GET /ready` | Liveness and database/corpus readiness |
| `GET /documents` | Active manifest and attribution |
| `GET /chunks/{id}` | Active source chunk and line provenance |
| `POST /ask` | `question`, `mode` (`vector` / `graph_vector`), optional `document_filter` |
| `GET /queries/{id}` | Full answer, evidence and measurements |
| `GET /queries/{id}/trace` | Observable stage records, fallback/error codes and timing |

No upload, deletion, arbitrary Cypher, LLM router, reranker or evaluation-run HTTP API is included.

## Evaluate honestly

Forty source-checked **draft** labels are included: 16 development and 24 test. Independent human
review is still required. Follow [evaluation/REVIEW.md](evaluation/REVIEW.md) before a release run.
Without `--allow-unreviewed`, evaluation refuses unreviewed labels and fixture graphs.

```sh
# Only after human review and LLM ingestion; generation is explicitly opt-in:
docker compose exec api nexusrag evaluate --split test --generate --repeats 3
# Fill the generated judgments.csv by inspecting the cited claims, then:
docker compose exec api nexusrag score results/runs/RUN_ID
```

Each run saves frozen configuration, raw paired outputs, retrieval metrics, timing summaries and
a human-judgment sheet. Metrics include Recall/Precision/MRR/nDCG at K=5/10/20 for vector candidates,
complete final-context evidence, entity/template matching and paired wins/ties/losses. Human
judgments add answer correctness, faithfulness, citation support/coverage and abstention quality.
No-answer evidence recall is null. P95 uses nearest rank with sample counts. Extraction usage is
reported separately from query usage. A valid citation ID is not proof that its claim is true.

## Verify

```sh
uv run ruff check src tests scripts migrations
uv run ruff format --check src tests scripts migrations
uv run mypy src
uv run pytest -q
RUN_INTEGRATION=1 uv run --env-file .env pytest -q tests/test_integration.py
RUN_MODEL=1 HF_HUB_OFFLINE=1 uv run --env-file .env pytest -q -m model
```

Tests mock paid calls. Integration tests use unique temporary corpus IDs in NexusRAG's dedicated
local databases and clean up only their own data. CI runs lint, types, unit/integration checks,
schema validation and image builds; it never spends money on model evaluations.

## Design and release status

- [Technical design and architecture diagram](docs/design.md)
- [Measured diagnostic and failure analysis](docs/report.md)
- [Three-minute demo script](docs/demo.md)
- [Corpus attribution and upstream license](corpus/ATTRIBUTION.md)

The application and evaluation tooling are implemented. Remaining release work is explicit:
configure the API key; run and review LLM extraction; independently review the forty gold labels;
run the held-out answer comparison; fill human judgments; record the demo video; choose a public
repository destination and tag the final measured release. No answer-quality improvement,
finished video, public repository or release tag is claimed yet.

Graph absence never proves real-world absence. Documented relationships do not prove outage
propagation. The existing service overview can make vector retrieval highly competitive. This
experiment compares graph augmentation against this vector baseline on this corpus only.

Implementation references: [BGE model card](https://huggingface.co/BAAI/bge-small-en-v1.5),
[pgvector](https://github.com/pgvector/pgvector),
[OpenAI model snapshot](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[structured output](https://developers.openai.com/api/docs/guides/structured-outputs), and
[uv CPU PyTorch configuration](https://docs.astral.sh/uv/guides/integration/pytorch/).
