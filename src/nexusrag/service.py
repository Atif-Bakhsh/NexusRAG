import time
import uuid
from contextlib import contextmanager

from nexusrag.config import Settings
from nexusrag.db import Repository
from nexusrag.generation.answers import answer_question
from nexusrag.generation.llm import LLM, token_count
from nexusrag.graph.ontology import Registry
from nexusrag.graph.planner import plan_question
from nexusrag.graph.store import GraphStore
from nexusrag.ingestion.corpus import digest
from nexusrag.models import Answer, AskRequest, Plan
from nexusrag.retrieval.context import select_context
from nexusrag.retrieval.embeddings import Embedder


@contextmanager
def timer(trace: dict, name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        trace.setdefault("latency_ms", {})[name] = (time.perf_counter() - start) * 1000


class QueryService:
    def __init__(
        self, settings: Settings, repository=None, embedder=None, graph=None, registry=None
    ):
        self.settings = settings
        self.repository = repository or Repository(settings)
        self.embedder = embedder or Embedder(settings)
        self.graph = graph or GraphStore(settings)
        self.registry = registry or Registry(settings.corpus_dir / "aliases.json")

    def ask(
        self,
        request: AskRequest,
        generate: bool = True,
        llm=None,
        *,
        expected_corpus_version: str | None = None,
    ) -> dict:
        started = time.perf_counter()
        active = self.repository.active()
        version = active.version
        if expected_corpus_version is not None and version != expected_corpus_version:
            raise RuntimeError("Active corpus changed during evaluation; discard this run")
        if request.document_filter is not None:
            allowed = {d["document_id"] for d in active.manifest["documents"]}
            if not set(request.document_filter) <= allowed:
                raise ValueError("Unknown document filter")
        llm = llm or LLM(self.settings)
        trace: dict = {
            "configuration": self.settings.fingerprint(),
            "ingestion_configuration": getattr(active, "configuration", {}),
            "errors": [],
            "fallbacks": [],
            "graph_truncated": False,
        }
        result: dict = {
            "query_id": str(uuid.uuid4()),
            "question": request.question,
            "mode": request.mode,
            "corpus_version": version,
            "answer": None,
            "evidence": [],
            "paths": [],
            "trace": trace,
            "generation_requested": generate,
        }
        try:
            indexed = getattr(active, "configuration", {})
            for key in ("embedding_model", "embedding_revision", "chunker_version"):
                if key in indexed and indexed[key] != getattr(self.settings, key):
                    raise ValueError("Active corpus settings mismatch; re-ingest the corpus")
            if indexed.get("aliases_sha256") and indexed["aliases_sha256"] != digest(
                (self.settings.corpus_dir / "aliases.json").read_bytes()
            ):
                raise ValueError("Alias map changed; re-ingest before querying")
            with timer(trace, "embedding"):
                vector = self.embedder.query(request.question)
            with timer(trace, "vector"):
                candidates = self.repository.search(
                    vector, version, self.settings.candidate_k, request.document_filter
                )
            trace["vector_candidates"] = [
                {"chunk_id": c.chunk_id, "score": score} for c, score in candidates
            ]
            plan = Plan(fallback_reason="vector_mode")
            paths = []
            if request.mode == "graph_vector":
                with timer(trace, "graph"):
                    plan = plan_question(request.question, self.registry)
                    if plan.template_id and not plan.clarification:
                        try:
                            if not self.graph.ready(version):
                                raise RuntimeError("graph_corpus_unavailable")
                            paths, truncated = self.graph.retrieve(plan, version)
                            trace["graph_truncated"] = truncated
                            if not paths:
                                trace["fallbacks"].append("no_path_found_in_graph")
                        except Exception as exc:
                            trace["errors"].append({"stage": "graph", "type": type(exc).__name__})
                            trace["fallbacks"].append("graph_failed_using_vector")
                    elif plan.fallback_reason:
                        trace["fallbacks"].append(plan.fallback_reason)
            trace["plan"] = plan.model_dump()
            trace["graph_candidates"] = [p.model_dump() for p in paths]
            with timer(trace, "context"):
                path_ids = list(dict.fromkeys(id_ for p in paths for id_ in p.chunk_ids))
                available = {c.chunk_id: c for c in self.repository.chunks(version, path_ids)}
                context, selected_paths, dropped = select_context(
                    [c for c, _ in candidates],
                    paths,
                    available,
                    token_count,
                    self.settings.context_chunks,
                    self.settings.context_tokens,
                    request.document_filter,
                )
            trace["context_ids"] = [c.chunk_id for c in context]
            trace["dropped_paths"] = dropped
            result["evidence"] = [c.model_dump() for c in context]
            result["paths"] = [p.model_dump() for p in selected_paths]
            if plan.clarification:
                answer = Answer(
                    status="clarification_needed", statements=[], limitations=[plan.clarification]
                )
                result["answer"] = answer.model_dump()
                trace["citation_validation"] = "not_applicable"
            elif generate:
                with timer(trace, "generation"):
                    answer, validation = answer_question(
                        llm, request.question, context, selected_paths, version
                    )
                result["answer"] = answer.model_dump()
                trace["citation_validation"] = validation
            else:
                trace["citation_validation"] = "retrieval_only"
            result["status"] = "completed"
        except Exception as exc:
            # Never expose provider errors, credentials, or database connection strings.
            result["status"] = "failed"
            trace["errors"].append({"stage": "query", "type": type(exc).__name__})
            trace["citation_validation"] = (
                "failed" if isinstance(exc, ValueError) else "not_completed"
            )
            result["error"] = "Query failed; inspect stage records and local configuration."
        trace["calls"] = llm.calls
        trace["estimated_cost_usd"] = sum(c.get("estimated_cost_usd") or 0 for c in llm.calls)
        trace["usage_complete"] = all(c.get("estimated_cost_usd") is not None for c in llm.calls)
        trace.setdefault("latency_ms", {})["total"] = (time.perf_counter() - started) * 1000
        self.repository.save_query(result)
        return result
