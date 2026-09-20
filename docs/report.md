# Initial development diagnostic — not the release benchmark

**Finding:** vector and fixture-graph augmentation tied at complete final-context evidence
for **11/12 answerable development questions (91.7%)**. Four clarification/unsupported questions
have undefined evidence recall. All 32 retrieval requests completed without query errors.

This is a real, unpaid retrieval diagnostic using BGE embeddings, PostgreSQL and Neo4j. It is
**not** evidence of LLM extraction quality, answer correctness, faithfulness or citation support.
Those stages require the API key and human review. No held-out test comparison has been run.

## Reproduce

```sh
uv run --env-file .env nexusrag ingest --fixture-graph
HF_HUB_OFFLINE=1 uv run --env-file .env nexusrag evaluate --split dev --allow-unreviewed
```

- Snapshot: `a471a5d079a2c4aa02283f606babf339acf4ff48`; 12 Markdown files, 128 chunks.
- Index: `astronomy-a471a5d079a2-bc8b978450`; 35 explicit Mermaid fixture assertions.
- BGE: `BAAI/bge-small-en-v1.5`, revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`.
- 16 development questions, one retrieval pass per mode, concurrency one.
- Gold labels: agent source-checked; independent human review pending.
- Context cap: 8 chunks / 3,000 serialized evidence tokens, at most two complete graph paths.
- macOS ARM host; PostgreSQL and Neo4j in local Docker. Model warmed with one query.
- Execution: 2026-09-20; raw outputs include full stage timings and configuration hashes.

[Configuration](../results/development-diagnostic/configuration.json),
[raw paired outputs](../results/development-diagnostic/raw.jsonl),
[summary](../results/development-diagnostic/summary.json).

## Evidence metrics

Both arms have the same vector candidates by design; graph evidence is added during final
context selection. These are candidate-ranking metrics, **not answer accuracy**.
Macro averages below use the twelve answerable questions. Repeated chunk IDs are deduplicated;
redundant alternative chunks still affect recall, so complete support is the main metric.

| Mode | K | Recall | Precision | MRR | nDCG | n |
|---|---:|---:|---:|---:|---:|---:|
| vector | 5 | 0.597 | 0.200 | 0.618 | 0.523 | 12 |
| vector | 10 | 0.736 | 0.133 | 0.618 | 0.583 | 12 |
| vector | 20 | 0.889 | 0.083 | 0.618 | 0.633 | 12 |
| graph_vector | 5 | 0.597 | 0.200 | 0.618 | 0.523 | 12 |
| graph_vector | 10 | 0.736 | 0.133 | 0.618 | 0.583 | 12 |
| graph_vector | 20 | 0.889 | 0.083 | 0.618 | 0.633 | 12 |

| Final-context category | Graph wins | Ties | Graph losses |
|---|---:|---:|---:|
| Lookup | 0 | 8 | 0 |
| Single hop | 0 | 1 | 0 |
| Two hop | 0 | 1 | 0 |
| Three hop | 0 | 2 | 0 |

Entity-set matching was exact on 15/16 development questions; template matching was 16/16.
The entity miss is “quotes,” which is not a canonical alias for Quote. The Shipping neighbor
query still retrieved the needed edge. No alias was added to erase this measured limitation.
Most lookup questions intentionally fall back to vector evidence, so graph-stage median timing
across every question is not representative of actual database traversal latency.

## Timing, tokens and cost

| Operation | Vector median / P95 | Graph + Vector median / P95 | n per arm |
|---|---:|---:|---:|
| Question embedding | 6.27 / 9.03 ms | 6.69 / 8.24 ms | 16 |
| Vector search | 3.75 / 10.37 ms | 3.67 / 6.72 ms | 16 |
| Retrieval pipeline total | 14.76 / 122.92 ms | 14.51 / 67.00 ms | 16 |

P95 is nearest rank. Total runs from active-corpus lookup through context/response assembly;
it excludes query-record persistence, HTTP transport, Streamlit rendering and model loading.
The first evidence-tokenizer initialization inflated one vector context-selection timing.
These small, mixed-warmth samples do not establish that graph retrieval is faster. Generation
latency is unmeasured. Generation tokens, extraction tokens and API spend were all **0**.
The fixture's initial ingestion took approximately 6.9 seconds including model load, embedding
and database import; this is not an LLM extraction-time measurement.

## Success, limitation and failure

**Success:** the constrained Frontend → Checkout → Shipping → Quote route includes three
supported edges and source chunks. Vector retrieval also found complete support; the explicit
architecture diagram was deliberately available to both systems.

**Limitation:** exact aliases miss inflected or implicit names. “quotes” did not match Quote.
Four graph-query families with paths of at most three hops are a bounded retrieval design, not general question
understanding. Shared dependencies can require more than the two selected paths; final-vector
fill may or may not supply the remaining evidence.

**Failure:** question 06 asks whether Frontend requires login. Its supporting fact is the
Frontend row in `services.md`, but that row was absent from the final eight chunks in both arms.
The graph planner correctly fell back to vector retrieval because login is outside the ontology.
This is a candidate-retrieval miss, not a measured hallucination: the supporting login row
was absent even from the top twenty candidates. A different overview chunk appeared at rank 12,
covering lines 21–28, while the login fact is on line 20. Chunk boundaries and semantic ranking
are therefore concrete follow-up candidates.

## What remains unmeasured

Human label agreement, semantic extraction precision/recall, the 24-question held-out comparison,
answer correctness, claim faithfulness, citation support/coverage, unnecessary abstention,
paid-model latency/cost and generation variability. The supplied scoring workflow leaves these
blank until reviewed. No graph-superiority claim or resume improvement percentage is justified.

This corpus is small and unusually explicit. Future reranking, lexical search or query
decomposition would be separate controlled baselines, not conclusions from this diagnostic.
