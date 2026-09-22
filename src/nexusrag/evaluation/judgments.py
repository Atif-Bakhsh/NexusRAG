"""Aggregate explicit human counts; never replace missing judgments with model scores."""

import csv
import json
from pathlib import Path


def ratio(n: int, d: int):
    return {"numerator": n, "denominator": d, "rate": n / d if d else None}


def score_judgments(run_dir: Path) -> dict:
    records = [json.loads(line) for line in (run_dir / "raw.jsonl").read_text().splitlines()]
    lookup = {r["result"]["query_id"]: r for r in records}
    with (run_dir / "judgments.csv").open() as f:
        judgments = list(csv.DictReader(f))
    if len(judgments) != len(lookup) or {j["query_id"] for j in judgments} != set(lookup):
        raise ValueError("Judgments must cover each query exactly once")
    fields = [
        "factual_claims",
        "supported_claims",
        "cited_claims",
        "supported_cited_claims",
        "claims_with_supporting_citations",
    ]
    for j in judgments:
        if not j["reviewer"].strip() or j["correct"] not in ("0", "1"):
            raise ValueError("Every judgment needs reviewer and correct=0 or 1")
        r = lookup[j["query_id"]]
        if not r["result"]["generation_requested"]:
            raise ValueError("Cannot score generation quality for a retrieval-only run")
        if (j["question_id"], j["repeat"], j["mode"]) != (
            r["question_id"],
            str(r["repeat"]),
            r["result"]["mode"],
        ):
            raise ValueError("Judgment identifiers do not match raw output")
        counts = {f: int(j[f]) for f in fields}
        if any(c < 0 for c in counts.values()):
            raise ValueError("Claim counts cannot be negative")
        if not (
            counts["supported_cited_claims"] <= counts["cited_claims"] <= counts["factual_claims"]
            and counts["claims_with_supporting_citations"]
            <= counts["supported_claims"]
            <= counts["factual_claims"]
            and counts["supported_cited_claims"] <= counts["supported_claims"]
            and counts["claims_with_supporting_citations"] <= counts["supported_cited_claims"]
        ):
            raise ValueError("Inconsistent claim counts")
        if j["failure_stage"] not in (
            "",
            "extraction",
            "resolution",
            "retrieval",
            "context_selection",
            "generation",
        ):
            raise ValueError("Unknown failure stage")
    output: dict = {"modes": {}, "paired_correctness_by_category": {}}
    for mode in ("vector", "graph_vector"):
        rows = [j for j in judgments if j["mode"] == mode]
        totals = {f: sum(int(j[f]) for j in rows) for f in fields}
        no_answer = [j for j in rows if lookup[j["query_id"]]["expected_behavior"] != "answered"]
        answerable = [j for j in rows if lookup[j["query_id"]]["expected_behavior"] == "answered"]

        def abstained(j):
            answer = lookup[j["query_id"]]["result"].get("answer")
            return bool(answer and answer["status"] != "answered")

        output["modes"][mode] = {
            "answer_correctness": ratio(sum(int(j["correct"]) for j in rows), len(rows)),
            "faithfulness": ratio(totals["supported_claims"], totals["factual_claims"]),
            "citation_support_precision": ratio(
                totals["supported_cited_claims"], totals["cited_claims"]
            ),
            "citation_coverage": ratio(
                totals["claims_with_supporting_citations"], totals["factual_claims"]
            ),
            "unsupported_claim_rate": ratio(
                totals["factual_claims"] - totals["supported_claims"], totals["factual_claims"]
            ),
            "correct_abstention": ratio(
                sum(abstained(j) and int(j["correct"]) for j in no_answer), len(no_answer)
            ),
            "unnecessary_abstention": ratio(sum(abstained(j) for j in answerable), len(answerable)),
            "failure_stages": {
                stage: sum(j["failure_stage"] == stage for j in rows)
                for stage in (
                    "extraction",
                    "resolution",
                    "retrieval",
                    "context_selection",
                    "generation",
                )
            },
        }
    pairs: dict = {}
    for j in judgments:
        category = lookup[j["query_id"]]["category"]
        pairs.setdefault((j["question_id"], j["repeat"], category), {})[j["mode"]] = int(
            j["correct"]
        )
    for (_, _, category), scores in pairs.items():
        if len(scores) != 2:
            continue
        counts = output["paired_correctness_by_category"].setdefault(
            category, dict(wins=0, ties=0, losses=0)
        )
        delta = scores["graph_vector"] - scores["vector"]
        counts["wins" if delta > 0 else "losses" if delta < 0 else "ties"] += 1
    (run_dir / "human_scores.json").write_text(json.dumps(output, indent=2))
    return output
