# Final live experiment protocol

**This is a future, paid workflow. It was not executed during the readiness pass.**
Use the free fixture workflow first. Do not report fixture performance as extraction quality
or answer correctness.

## 1. Review labels and freeze the experiment

Read [evaluation/REVIEW.md](../evaluation/REVIEW.md). Independently review all 40 gold answers,
source spans, alternative evidence sets, relationship directions and expected abstentions.
Record the real reviewer and human_reviewed status only after review. Question 02's .NET/C#
distinction is explicitly unresolved. Do not run author_labels.py over reviewed labels.

Use the 16 development questions for changes; keep the 24 test questions held out.
Keep related route groups together. Check source support, not just exact quote matches.

```sh
docker compose exec -T api nexusrag validate
git rev-parse HEAD
git status --short
```

Commit reviewed labels/configuration before the final run, then rebuild api/ui because
evaluation files and prompts are copied into images. Record the code commit alongside the run.
Do not ingest another version while evaluation is running.

## 2. Configure intentional live access

Edit the ignored .env locally:

```dotenv
OPENAI_API_KEY=your-own-project-key
DISABLE_PAID_API=false
GENERATION_MODEL=gpt-5.4-mini-2026-03-17
API_BUDGET_USD=50
INPUT_USD_PER_MILLION=0.75
OUTPUT_USD_PER_MILLION=4.50
```

Use a dedicated provider project. Verify model access and current pricing before execution;
the rates above are the existing planning estimates. Keep the spend ledger and budget cap.
Do not put the real key in shell arguments, screenshots, results or Git.

```sh
docker compose up -d --build --wait
docker compose exec -T api nexusrag preflight --require-generation
```

Preflight only checks local configuration and prerequisites. It does not verify a key with
OpenAI and never spends money. Do not use make up here: that target deliberately disables
paid calls.

## 3. Run and review LLM extraction

```sh
# PAID: omit --fixture-graph.
docker compose exec -T api nexusrag ingest
docker compose exec -T api nexusrag preflight --require-ready --require-generation
curl --fail http://127.0.0.1:58000/ready
```

Confirm graph_source is llm and note the new corpus_version. Inspect that version's
artifacts/INDEX_VERSION/ingestion.json, assertions.jsonl, chunks.jsonl and extraction_calls.jsonl.
A new LLM version has different IDs from the fixture. The existing fixture remains historical.

Review every assertion against its source: entities, direction, predicate, quote and entailment.
Record accepted/rejected edges and omissions in a reviewer-owned review file next to the
export, plus reviewer/date. Compare source relationships with extracted relationships;
count duplicates or multiple evidence assertions separately from unique semantic edges.

Preflight validates structure and provenance, not semantic correctness. An LLM source flag
also does not mean human-reviewed. Do not hand-edit model-produced edges and then claim the
result is untouched extraction. If correcting the ontology/prompt, increment its version,
rerun on development evidence, and report the change and additional extraction cost.
Human graph review is a procedural release gate, not an automatic flag enforced by the CLI.

Inspect in Neo4j Browser, replacing VERSION:

```cypher
MATCH (c:Corpus {version:'VERSION'}) RETURN c;
MATCH (a:Entity {corpus_version:'VERSION'})-[r]->(b:Entity)
RETURN a.entity_id, type(r), b.entity_id, r.payload;
```

A failed extraction stops ingestion and leaves the version unavailable. Correct the cause
and rerun the same settings to reuse valid chunk caches. There is no automatic extraction
repair loop. Never delete spend.sqlite to get past a budget error.

## 4. Development validation, then held-out comparison

First run development retrieval and, if needed, development answers. These are separate
runs from the held-out measurement:

```sh
docker compose exec -T api nexusrag evaluate --split dev
# PAID:
docker compose exec -T api nexusrag evaluate --split dev --generate
```

Freeze settings after development. Run the reviewed held-out comparison:

```sh
# Free retrieval-only held-out measurement, after the experiment is frozen:
docker compose exec -T api nexusrag evaluate --split test
# PAID: 24 questions × 2 modes × 3 repetitions:
docker compose exec -T api nexusrag evaluate --split test --generate --repeats 3
```

One repetition uses --repeats 1. Do not combine different settings in one result table as if
they were the same run. Never use --allow-unreviewed for the final result.

The runner alternates arm order and records settings, ingestion configuration, label hash,
a label snapshot, hardware metadata, concurrency and warmup. Preserve all raw JSONL, summary,
judgment CSV and code commit. Query records also remain in PostgreSQL.

## 5. Call-count and budget planning

| Operation | Calls calculated from the code |
| --- | --- |
| Fresh extraction of the current 128 chunks | 128 normal calls, one per uncached chunk, including chunks yielding zero edges |
| Reusing complete validated extraction cache/export | 0 extraction calls |
| 24 held-out questions × 2 modes × 1 repeat | Up to 48 normal generation calls |
| 24 held-out questions × 2 modes × 3 repeats | Up to 144 normal generation calls |
| Repairs in a three-repeat held-out run | At most one additional call per generated answer: up to 288 total generation calls |
| Fresh extraction + three-repeat held-out generation | Up to 272 normal calls; up to 416 including every possible generation repair |
| Compare in the UI | Normally 2 generation calls, up to 4 with repairs |

Deterministic clarification can reduce calls; failures/budget stops can end runs early.
Changing chunking changes extraction counts. Cached ingestion and ready-version no-ops also
reduce calls. SDK retries are disabled; manually repeating a failed command can incur costs.

For planning only, 5,000 input and 700 output tokens at the configured rates cost $0.0069 per
answer: 144 such calls are about $0.99, excluding extraction, repairs and development runs.
This is not a measured bill. Extraction uses a 4,000-output-token cap; normal answers use 1,800.
Report recorded usage and extraction cost separately. Unknown usage retains a reservation
and must not be silently counted as a measured zero.

## 6. Human judgments and scoring

Open results/runs/RUN_ID/judgments.csv and inspect each corresponding raw answer and context.
Do not edit the identifying columns. Fill:

- correct: 0 or 1 against the reviewed gold rubric.
- factual_claims: all factual claims, including facts in limitations.
- supported_claims: claims entailed by the supplied context.
- cited_claims: factual claims that include citations.
- supported_cited_claims: cited claims supported by their own citations.
- claims_with_supporting_citations: factual claims with sufficient citation support.
- failure_stage: blank or extraction, resolution, retrieval, context_selection, generation.
- notes and the actual reviewer.

Count each claim once even when it cites several chunks. Correctness and faithfulness differ:
an answer can match a fact while lacking support in the supplied evidence. Treat invalid or
failed answers as failures, not automatic abstentions. Nonfactual abstention text has zero
factual claims; explanatory factual assertions still need evaluation. Blind reviewers to
mode where practical to reduce preference bias.

```sh
# Free, after all judgments are complete:
docker compose exec -T api nexusrag score results/runs/RUN_ID
```

The scorer rejects incomplete reviews, mismatched IDs and inconsistent counts. It creates
human_scores.json and cannot score retrieval-only runs as generation quality.

## 7. Interpret and publish honestly

Hold constant corpus, chunks, model revision, generator, grounding prompt, output cap,
8-chunk/3,000-token budget, machine and concurrency. Both modes retain Mermaid source.
Graph mode adds complete source bundles, not extra context budget.

Report counts with percentages, paired wins/ties/losses by category, complete evidence,
human correctness, faithfulness, citation support and both kinds of abstention. No-answer
recall is undefined. Repetitions are repeated observations of 24 questions, not 72 new questions.

Total latency measures service processing through result assembly, excluding HTTP transport
and query-record persistence. Stage timing and nearest-rank P95 include sample counts.
Do not infer graph speed from the small historical diagnostic with asymmetric cold effects.

Inspect failures at their earliest cause. Distinguish missing extraction from planner errors,
retrieval misses, path-bundle budget drops and unsupported generated claims. Report graph ties
or regressions. This compares graph augmentation against this vector baseline; it does not
establish superiority over lexical retrieval, reranking or iterative retrieval.

Before a measured release: update README and report using actual outputs, retain attribution,
scan publishable artifacts for secrets/private queries, record the demo, and tag the reviewed
commit. Disable paid access again after the experiment:
set DISABLE_PAID_API=true and recreate api. Do not claim a completed release from fixture data.
