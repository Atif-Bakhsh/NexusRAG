import csv
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

from nexusrag.config import Settings
from nexusrag.evaluation.metrics import distribution, map_gold, ranking_metrics
from nexusrag.evaluation.schema import Question
from nexusrag.ingestion.corpus import digest, load_corpus
from nexusrag.models import AskRequest
from nexusrag.service import QueryService


def load_questions(path: Path, settings: Settings) -> list[Question]:
    questions = [
        Question.model_validate_json(line) for line in path.read_text().splitlines() if line
    ]
    if len(questions) != 40 or len({q.id for q in questions}) != 40:
        raise ValueError("Expected forty distinct labeled questions")
    _, documents = load_corpus(settings.corpus_dir)
    groups: dict[str, str] = {}
    for q in questions:
        if q.group in groups and groups[q.group] != q.split:
            raise ValueError("Related question group leaked across splits")
        groups[q.group] = q.split
        if q.expected_behavior == "answered" and not q.evidence_sets:
            raise ValueError(f"Answerable question {q.id} lacks source labels")
        if q.review_status == "human_reviewed" and not q.reviewer:
            raise ValueError("Human review requires a named reviewer")
        for spans in q.evidence_sets:
            for span in spans:
                lines = documents[span.document_id].splitlines(keepends=True)
                if span.line_end < span.line_start or span.line_end > len(lines):
                    raise ValueError("Invalid gold source lines")
                if "".join(lines[span.line_start - 1 : span.line_end]) != span.quote:
                    raise ValueError(f"Gold quote mismatch: {q.id}")
    return questions


def run(
    settings: Settings,
    split: str = "dev",
    generate: bool = False,
    repeats: int = 1,
    allow_unreviewed: bool = False,
) -> Path:
    labels_path = Path("evaluation/questions.jsonl")
    questions = [q for q in load_questions(labels_path, settings) if q.split == split]
    unreviewed = any(q.review_status != "human_reviewed" for q in questions)
    if unreviewed and not allow_unreviewed:
        raise ValueError(
            "Human label review is pending. Use --allow-unreviewed only for diagnostics."
        )
    svc = QueryService(settings)
    active = svc.repository.active()
    chunks = svc.repository.chunks(active.version)
    if not allow_unreviewed and active.configuration.get("graph_source") != "llm":
        raise ValueError(
            "Release benchmark requires the LLM-extracted graph, not the smoke fixture"
        )
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = settings.results_dir / now
    output.mkdir(parents=True)
    configuration = {
        "settings": settings.fingerprint(),
        "corpus_version": active.version,
        "ingestion_configuration": active.configuration,
        "labels_sha256": digest(labels_path.read_bytes()),
        "split": split,
        "generation": generate,
        "repeats": repeats,
        "human_labels_complete": not unreviewed,
        "diagnostic_only": unreviewed or allow_unreviewed,
        "hardware": {"platform": platform.platform(), "processor": platform.processor()},
        "concurrency": 1,
        "warmup": "one embedding; no database-query warmup",
    }
    (output / "configuration.json").write_text(json.dumps(configuration, indent=2))
    records = []
    svc.embedder.query("warmup")
    try:
        with (output / "raw.jsonl").open("w") as raw:
            for repeat in range(repeats):
                for index, question in enumerate(questions):
                    relevance, sets = map_gold(question, chunks)
                    if any(not cover for support in sets for cover in support):
                        raise ValueError(
                            f"Unmapped gold span in {question.id}; fix chunk/span mapping"
                        )
                    # Alternate which arm runs first to reduce warm-cache order bias.
                    modes = (
                        ["vector", "graph_vector"]
                        if (index + repeat) % 2 == 0
                        else ["graph_vector", "vector"]
                    )
                    for mode in modes:
                        result = svc.ask(
                            AskRequest.model_validate(dict(question=question.question, mode=mode)),
                            generate=generate,
                        )
                        trace = result["trace"]
                        candidate_ids = [c["chunk_id"] for c in trace.get("vector_candidates", [])]
                        metrics: dict = {
                            f"vector_candidates@{k}": ranking_metrics(
                                candidate_ids, relevance, sets, k
                            )
                            for k in (5, 10, 20)
                        }
                        metrics["final_context"] = ranking_metrics(
                            trace.get("context_ids", []), relevance, sets, 8
                        )
                        plan = trace.get("plan", {})
                        metrics["entity_match_exact"] = (
                            set(plan.get("matched_entities", [])) == set(question.gold_entities)
                            if mode == "graph_vector"
                            else None
                        )
                        metrics["template_match"] = (
                            plan.get("template_id") == question.gold_template
                            if mode == "graph_vector"
                            else None
                        )
                        record: dict = {
                            "question_id": question.id,
                            "category": question.category,
                            "repeat": repeat,
                            "expected_behavior": question.expected_behavior,
                            "metrics": metrics,
                            "result": result,
                        }
                        records.append(record)
                        raw.write(json.dumps(record) + "\n")
                        raw.flush()
    finally:
        svc.graph.close()
    summary = summarize(records)
    summary["configuration"] = configuration
    summary["generation_quality"] = "pending human judgments" if generate else "not measured"
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    with (output / "judgments.csv").open("w") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "question_id",
                "repeat",
                "mode",
                "query_id",
                "correct",
                "factual_claims",
                "supported_claims",
                "cited_claims",
                "supported_cited_claims",
                "claims_with_supporting_citations",
                "failure_stage",
                "notes",
                "reviewer",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "question_id": record["question_id"],
                    "repeat": record["repeat"],
                    "mode": record["result"]["mode"],
                    "query_id": record["result"]["query_id"],
                }
            )
    return output


def summarize(records: list[dict]) -> dict:
    summary: dict = {"modes": {}, "paired_complete_evidence_by_category": {}}
    for mode in ("vector", "graph_vector"):
        rows = [r for r in records if r["result"]["mode"] == mode]
        metrics = [
            r["metrics"]["final_context"]["complete_evidence"]
            for r in rows
            if r["metrics"]["final_context"]["complete_evidence"] is not None
        ]
        summary["modes"][mode] = {
            "queries": len(rows),
            "failures": sum(r["result"]["status"] != "completed" for r in rows),
            "complete_evidence": {
                "successes": sum(metrics),
                "n": len(metrics),
                "rate": sum(metrics) / len(metrics) if metrics else None,
            },
            "latency_ms": {
                stage: distribution(
                    [
                        r["result"]["trace"]["latency_ms"][stage]
                        for r in rows
                        if stage in r["result"]["trace"]["latency_ms"]
                    ]
                )
                for stage in ("embedding", "vector", "graph", "context", "generation", "total")
            },
            "estimated_cost_usd": sum(r["result"]["trace"]["estimated_cost_usd"] for r in rows),
        }
    pairs: dict = {}
    for r in records:
        pairs.setdefault((r["question_id"], r["repeat"], r["category"]), {})[
            r["result"]["mode"]
        ] = r
    for (_, _, category), pair in pairs.items():
        if len(pair) != 2:
            continue
        a, b = [
            pair[m]["metrics"]["final_context"]["complete_evidence"]
            for m in ("vector", "graph_vector")
        ]
        if a is None or b is None:
            continue
        counts = summary["paired_complete_evidence_by_category"].setdefault(
            category, {"wins": 0, "ties": 0, "losses": 0}
        )
        counts["wins" if b > a else "losses" if b < a else "ties"] += 1
    return summary
