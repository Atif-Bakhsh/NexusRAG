# Troubleshooting

Start with `docker compose ps` and
`docker compose exec -T api nexusrag preflight --require-ready`.
If api cannot start, inspect `docker compose logs --tail=80 api`.
Do not publish .env, expanded Compose configuration, or logs containing connection secrets.

| Symptom | Check | Recovery |
| --- | --- | --- |
| Docker daemon unavailable | `docker info` | Start Docker Desktop; on Linux start the Docker service and check socket permissions |
| Containers exit or start slowly | `docker compose ps`; service logs | Allow initial downloads to finish; allocate adequate Docker memory; verify disk space |
| PostgreSQL unavailable | `docker compose exec postgres pg_isready -U nexusrag -d nexusrag` | Start postgres; host port is 55433, container port 5432; check DATABASE_URL password |
| Neo4j unavailable | Neo4j logs and preflight | Start neo4j; host Bolt 57687, container 7687. Use neo4j and NEO4J_PASSWORD; allow startup recovery |
| Port already allocated | `lsof -nP -iTCP:58000 -sTCP:LISTEN` (replace port as needed) | Stop the duplicate host API/UI or conflicting service. Ports: 55433, 57474, 57687, 58000, 58501 |
| Model missing/download fails | preflight embedding_model result | Run download-model in the same host/container environment. Unset HF_HUB_OFFLINE while downloading; check network, disk and cache permissions |
| Tokenizer tries network offline | TIKTOKEN_CACHE_DIR differs from download environment | Run download-model with the same cache directory before offline retrieval |
| Corpus checksum/source failure | `nexusrag validate` | Restore changed corpus files from the intended Git revision. Do not rewrite hashes merely to accept an accidental edit |
| Migration failure or missing vector extension | `alembic current`; PostgreSQL logs | Use the pinned pgvector image and run alembic upgrade head against the intended database |
| Missing API key / paid_api_disabled | preflight generation check | Free retrieval remains usable. For the later live experiment only, set key and DISABLE_PAID_API=false, then recreate api |
| OpenAI timeout, malformed output or rejected model | Query trace errors/calls, not hidden reasoning | Verify model/account access separately during the live experiment. Check available budget. One schema/citation repair is allowed; provider errors have no SDK retry |
| Ingestion stops partway | CLI error and artifacts/INDEX_VERSION | Fix the stated source/config problem, then rerun identical settings. Validated extraction caches are reused. Failed new versions remain unavailable |
| Extraction quote/type/ID validation failure | Cached source chunk and assertion artifact | Review the exact excerpt, direction, canonical IDs and corpus. Never weaken validation to accept unsupported edges. Cache may be absent if that chunk failed validation |
| Retrieval returns no evidence | /ready, active corpus, document filter, trace.vector_candidates | Ingest a ready corpus; remove an unintended filter; verify the pinned model/alias settings match ingestion |
| Graph paths absent | trace.plan, fallbacks and dropped_paths | Unsupported phrasing legitimately falls back. Check aliases, template choice, hop limits and complete-bundle budget. No path is not proof of no dependency |
| Graph count/provenance mismatch | preflight graph_state; Neo4j inspection queries | Rebuild with the matching validated export or fixture ingestion. Keep prior artifacts. Do not mark a corrupt graph ready manually |
| Streamlit cannot contact FastAPI | /health and API_BASE_URL | Host UI uses 127.0.0.1:58000; container UI uses http://api:8000. Recreate ui after configuration changes |
| HTTP 429 | Another query is running | Wait for that request to finish, then retry. CLI evaluation should run at concurrency one |
| HTTP 502 from /ask | GET /queries/ID/trace from error's query ID | Generation failed or is disabled. Inspect sanitized stage errors; use retrieval-only CLI for the free workflow |
| Settings changed but container ignores them | Compare CONFIGURATION.md forwarding list | Recreate api for forwarded variables. Other settings need explicit exec -e or a Compose override |
| Changed DB password with old volumes | Authentication fails despite healthy process | Initialization environment does not rotate stored passwords. Restore the existing credentials or follow a deliberate reset after backup |
| Stale volumes/index version | PostgreSQL corpora and Neo4j Corpus markers | Latest created ready corpus is active. Rebuild with matching settings; use RUNBOOK's destructive reset only after preserving data |
| Repository moved/renamed | Old paths in entrypoints or container mounts | Run uv sync --frozen --extra dev --reinstall; run docker compose up -d --build --wait from the new root |
| Preflight warns about fixture/human review | graph_source / human_review checks | Expected in the free demo. Only actual human review and later LLM ingestion can resolve these release gates |
| Benchmark refuses to run | Draft labels or fixture active | Use --allow-unreviewed only for development diagnostics. Do not bypass it for the final held-out claim |
| Scoring rejects CSV | Missing reviewer, inconsistent counts/IDs or retrieval-only run | Complete real judgments without changing query IDs. Score only generated-answer runs |

Preflight returns exit 1 for failures and 0 for successful checks with possible warnings.
--require-ready and --require-generation promote missing requested prerequisites to failures.
It checks configuration, not provider credentials or billing validity.

For destructive reset commands and preservation of artifacts/spend.sqlite, use
[RUNBOOK.md](RUNBOOK.md#stop-restart-and-rebuild). A reset is not a first response to an
authentication error. A public server would need additional controls outside this local scope.
