# Project state

Assessed on 2026-10-29 from the local checkout. This document supersedes the September
completion report for current implementation status; that report remains historical evidence.

**Phase: working local research prototype, with the final experiment pending.**
The free evidence-search demo is implemented across CLI, HTTP API and Streamlit.
Generated-answer quality and live extraction quality have not been established.

## Implemented

| Area | Current behavior |
| --- | --- |
| Corpus | 12 commit-pinned Markdown documents with checksums and source-line provenance |
| Ingestion | Versioned, idempotent chunk/vector/graph ingestion; validated extraction caches and portable exports |
| Retrieval | BGE/pgvector baseline and graph + vector; four bounded graph-query families; equal context budgets |
| Local demo | 128 chunks and 35 Mermaid fixture assertions; no provider key required |
| API/UI | Evidence search, independent comparison, saved query inspection, graph paths and benchmark display |
| Generation | Structured provider integration, citation checks, one repair, spend reservations and paid-call disable switch |
| Evaluation | 40 labeled questions, grouped 16/24 development/test split, paired runs and explicit human scoring |
| Operations | Compose, migrations, read-only preflight, CI and free end-to-end smoke script |

The generation integration is implemented and tested with mocked provider transport. That does
not establish actual provider access, extraction entailment or generated-answer correctness.

## Changes in this continuation

- Added `POST /ask?generate=false`, reusing the existing retrieval service and saved-record shape.
  API clients omitting the parameter retain the previous generation behavior.
- Made Streamlit Ask / Compare default to evidence search. Answer generation requires explicit
  selection and server configuration. Retrieval results expose source passages, paths and timings.
- Added API/UI regression coverage and extended the real smoke script to exercise both HTTP
  retrieval modes with zero provider calls.
- Repaired the moved local Python environment using the unchanged dependency lock, and started
  the local databases for verification. No dependency upgrade or schema change was introduced.

## Evidence and limits

The retained [development diagnostic](report.md) found complete labeled evidence for **11/12
answerable development questions in each mode (91.7%)**. This is a tie on a small development
set using draft labels and the Mermaid fixture. It establishes neither a graph advantage nor
answer quality. All 40 labels still await independent human review.

Verification performed for this continuation:

| Check | Result |
| --- | --- |
| Ruff lint and formatting | Passed; 41 Python files |
| mypy | Passed; 24 source files |
| Default test suite | 61 passed; 7 database/model tests skipped as intended |
| Database and cached-model verification | 12 passed with real PostgreSQL, Neo4j and pinned BGE |
| Corpus/label validation | 12 documents; 40 valid labels; 0 human-reviewed |
| Focused API/UI coverage | 15 passed, including free comparison and explicit generation selection |
| Docker API/UI rebuild and four-service health | Passed on retry after Docker's daemon exited during the first build |
| Container preflight --require-ready | Passed; 128 chunks, 35 source-valid fixture assertions; expected review/generation warnings |
| End-to-end smoke | Passed; CLI and HTTP retrieval in both modes, graph support, saved records and API/UI health; zero provider calls |
| git diff --check | Passed |

Two existing Starlette/AnyIO deprecation warnings remain. Local environment repair is not a
new scientific measurement. The held-out test split is reserved for the final experiment.

The stack is running locally at [Streamlit](http://127.0.0.1:58501) and
[API docs](http://127.0.0.1:58000/docs). Live browser inspection was unavailable in this session;
UI interaction was verified with Streamlit AppTest and the running UI health endpoint.

## Next milestones

1. Independently review all 40 labels and resolve the documented .NET/C# ambiguity. Record the
   actual reviewer; agent source checking cannot replace this step.
2. Configure intentional live provider access, verify current model access/pricing, then run
   LLM extraction and review assertion meaning, direction and omissions against the sources.
3. Finish development validation, freeze code/settings/labels, and evaluate the 24 held-out
   questions with both modes. Complete genuine human judgments and publish measured results.
4. Choose the original-code license, record the demo and tag the measured release.

Follow [FINAL-EXPERIMENT.md](FINAL-EXPERIMENT.md) for execution. A measured graph improvement
is not required for an honest result. This remains a local application; public-service
deployment is a separate scope.
