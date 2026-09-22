# Resume wording supported by the repository

## Project entry

**NexusRAG — Evidence-backed RAG for Architecture Documentation**
Python, FastAPI, Streamlit, PostgreSQL/pgvector, Neo4j, Sentence Transformers/BGE, OpenAI SDK,
SQLAlchemy, Alembic, Docker Compose, pytest, GitHub Actions.

- Built a local RAG application over **12 commit-pinned Markdown documents**, indexing **128
  source-located chunks** with **384-dimensional BGE embeddings** and exact pgvector search.
- Implemented **2 retrieval modes** and **4 bounded graph-query families**, preserving source
  evidence for a **35-assertion fixture graph** with **3-hop** and **20-path** limits.
- Designed a **40-question evaluation set** with a **16/24 development/test split**; a free
  development diagnostic found complete evidence for **11/12 answerable questions (91.7%)**
  in both modes, identifying a tie rather than claiming a graph improvement.

Use two or three bullets to fit the available space. The third is deliberately described as
retrieval evidence, not answer accuracy. If interview space is limited, the first two are the
clearest implementation claims.

## Short description

Built a reproducible architecture-documentation assistant comparing vector and graph-augmented
retrieval across 12 documents, with provenance-backed graph paths, structured citation validation,
and a 40-question evaluation workflow.

## Skills demonstrated

Python backend development; REST APIs and Pydantic validation; PostgreSQL schema design and
Alembic migrations; exact vector similarity search; embedding tokenization and chunking;
Neo4j/Cypher and directed relationship modeling; provenance and citation validation;
retrieval evaluation; Docker Compose; automated testing; GitHub Actions; structured usage
and latency records; experiment design and technical documentation.

The code integrates structured OpenAI generation and a budget ledger. Live API reliability,
extraction quality and generated-answer quality remain unverified, so describe those as
implemented integrations rather than measured production outcomes.

## Claims to avoid

Do not claim improved accuracy, production deployment, real users, enterprise scale,
human-reviewed labels, a completed live LLM benchmark, or a measured answer-quality percentage.
Do not describe 144 repeated answer runs as 144 independent test questions. The 35 current
relationships are fixture assertions, not LLM-extracted assertions.

Numbers should make the engineering work concrete; they do not guarantee ATS ranking.
After the final experiment, replace the diagnostic bullet with actual held-out counts,
human-scored correctness and measured cost/latency tradeoffs—even if the graph ties or loses.

## GitHub presentation

The public repository has a relevant About description and a passing initial CI run.
This pass adds a free-first README, workflow badge, architecture, runbook, troubleshooting,
demo and explicit experiment status. Pin it on your profile if it is a featured project.

Remaining presentation work: choose an original-code license, record the actual demo, add its
link to README/About, and publish a measured release only after human review and the live
experiment. Suggested topics: rag, knowledge-graph, neo4j, pgvector, fastapi, information-retrieval.
No stars, users or releases are prerequisites for presenting honest engineering work.
