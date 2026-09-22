"""Read-only local diagnostics. Never instantiate an LLM or download model files."""

import math
import sys
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from nexusrag.config import Settings
from nexusrag.db import Repository
from nexusrag.evaluation.runner import load_questions
from nexusrag.graph.ontology import Registry, validate_extraction
from nexusrag.graph.store import GraphStore
from nexusrag.ingestion.corpus import digest, load_corpus
from nexusrag.models import Extraction
from nexusrag.retrieval.embeddings import Embedder


def run(settings: Settings, require_ready: bool = False, require_generation: bool = False) -> dict:
    checks: list[dict] = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    def check(name, operation, hint):
        try:
            add(name, "pass", operation())
            return True
        except Exception as exc:
            # Connection/provider exceptions can contain credentials. Emit only the class.
            add(name, "fail", f"{hint} ({type(exc).__name__})")
            return False

    add(
        "environment",
        "pass" if sys.version_info[:2] == (3, 12) else "fail",
        "Python 3.12 required; settings validated; secrets omitted.",
    )
    check(
        "corpus",
        lambda: f"{len(load_corpus(settings.corpus_dir)[0].documents)} verified documents",
        "Run nexusrag validate; restore the pinned manifest/files.",
    )

    def labels():
        rows = load_questions(Path("evaluation/questions.jsonl"), settings)
        reviewed = sum(q.review_status == "human_reviewed" for q in rows)
        add(
            "human_review",
            "pass" if reviewed == len(rows) else "warn",
            f"{reviewed}/{len(rows)} labels human-reviewed; required before release evaluation.",
        )
        return f"{len(rows)} source-span labels validated"

    check("evaluation", labels, "Review evaluation/questions.jsonl source spans and split groups.")
    check(
        "aliases",
        lambda: f"{len(Registry(settings.corpus_dir / 'aliases.json').entities)} entities",
        "Repair invalid or colliding aliases.",
    )
    repository = None
    active = None
    try:

        def postgres():
            nonlocal repository
            repository = Repository(settings)
            repository.ping()
            return "PostgreSQL connection authenticated"

        if check("postgresql", postgres, "Start postgres; check DATABASE_URL and credentials."):
            assert repository is not None

            def vector():
                with repository.engine.connect() as conn:
                    version = conn.scalar(
                        text("SELECT extversion FROM pg_extension WHERE extname='vector'")
                    )
                    if version is None:
                        raise ValueError("missing vector")
                    return f"pgvector {version}"

            check("pgvector", vector, "Run alembic upgrade head against the pgvector image.")

            def migrations():
                heads = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
                with repository.engine.connect() as conn:
                    current = set(MigrationContext.configure(conn).get_current_heads())
                if current != heads:
                    raise ValueError("migration mismatch")
                return "Database matches migration heads: " + ", ".join(sorted(heads))

            check("migrations", migrations, "Run alembic upgrade head; inspect alembic current.")
            try:
                active = repository.active()
                chunks = repository.chunks(active.version)
                if not chunks:
                    raise ValueError("empty corpus")
                for key in ("embedding_model", "embedding_revision", "chunker_version"):
                    if active.configuration.get(key) != getattr(settings, key):
                        raise ValueError("index settings mismatch")
                if active.configuration.get("aliases_sha256") != digest(
                    (settings.corpus_dir / "aliases.json").read_bytes()
                ):
                    raise ValueError("index aliases mismatch")
                add("active_corpus", "pass", f"{active.version}: {len(chunks)} chunks")
            except LookupError:
                add(
                    "active_corpus",
                    "fail" if require_ready else "warn",
                    "No ready corpus; run fixture ingestion or the planned live ingestion.",
                )
            except Exception as exc:
                active = None
                add("active_corpus", "fail", f"Re-ingest matching settings ({type(exc).__name__}).")

        graph = None
        try:

            def neo4j():
                nonlocal graph
                graph = GraphStore(settings)
                graph.ping()
                return "Neo4j connection authenticated"

            if check("neo4j", neo4j, "Start neo4j; check URI, user and password."):
                assert graph is not None
                if active is None:
                    add(
                        "graph_state",
                        "fail" if require_ready else "warn",
                        "No active PostgreSQL corpus available for graph checks.",
                    )
                else:

                    def graph_state():
                        assert repository is not None
                        if not graph.ready(active.version):
                            raise ValueError("marker/count mismatch")
                        chunks_by_id = {c.chunk_id: c for c in repository.chunks(active.version)}
                        registry = Registry(settings.corpus_dir / "aliases.json")
                        assertions = graph.assertions(active.version)
                        for assertion in assertions:
                            raw = Extraction.model_validate(
                                {
                                    "assertions": [
                                        assertion.model_dump(
                                            include={
                                                "subject",
                                                "predicate",
                                                "object",
                                                "evidence",
                                                "confidence_uncalibrated",
                                            }
                                        )
                                    ]
                                }
                            )
                            validated = validate_extraction(
                                raw,
                                chunks_by_id,
                                registry,
                                active.version,
                                assertion.extraction_model,
                                assertion.prompt_version,
                            )
                            if (
                                assertion.corpus_version != active.version
                                or assertion.assertion_id != validated[0].assertion_id
                            ):
                                raise ValueError("assertion identity mismatch")
                        source = active.configuration.get("graph_source", "unknown")
                        add(
                            "graph_source",
                            "pass" if source == "llm" else "warn",
                            f"{source}; structural validation does not verify semantic correctness.",
                        )
                        return (
                            f"{len(assertions)} assertions; all source references and quotes valid"
                        )

                    check(
                        "graph_state",
                        graph_state,
                        "Graph incomplete or invalid; rebuild from validated assertions.",
                    )
        finally:
            if graph is not None:
                graph.close()
    finally:
        if repository is not None:
            repository.engine.dispose()

    def embedding():
        vector = Embedder(settings, local_files_only=True).query("NexusRAG readiness check")
        if len(vector) != 384 or not math.isclose(sum(v * v for v in vector), 1, abs_tol=0.001):
            raise ValueError("invalid embedding")
        return "Pinned BGE model available locally; normalized 384-dimensional CPU embedding"

    check("embedding_model", embedding, "Run nexusrag download-model in this environment/cache.")
    configured = bool(settings.openai_api_key.get_secret_value()) and not settings.disable_paid_api
    add(
        "generation",
        "pass" if configured else ("fail" if require_generation else "warn"),
        "Configured; provider access and model availability NOT tested."
        if configured
        else "Paid calls disabled or OPENAI_API_KEY missing; retrieval-only operations remain available.",
    )
    return {
        "status": "failed" if any(c["status"] == "fail" for c in checks) else "ok",
        "paid_calls": 0,
        "checks": checks,
    }
