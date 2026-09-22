import csv
import json

import pytest

from nexusrag.evaluation.judgments import score_judgments


def write_fixture(path, reviewer="Human reviewer"):
    records = []
    judgments = []
    for mode in ["vector", "graph_vector"]:
        records.append(
            dict(
                question_id="01",
                repeat=0,
                category="lookup",
                expected_behavior="answered",
                result=dict(
                    query_id=mode,
                    mode=mode,
                    generation_requested=True,
                    answer=dict(status="answered"),
                ),
            )
        )
        judgments.append(
            dict(
                question_id="01",
                repeat="0",
                mode=mode,
                query_id=mode,
                correct="1",
                factual_claims="2",
                supported_claims="1",
                cited_claims="2",
                supported_cited_claims="1",
                claims_with_supporting_citations="1",
                failure_stage="generation",
                notes="",
                reviewer=reviewer,
            )
        )
    (path / "raw.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    with (path / "judgments.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(judgments[0]))
        writer.writeheader()
        writer.writerows(judgments)


def test_human_metrics_distinguish_correctness_from_faithfulness(tmp_path):
    write_fixture(tmp_path)
    output = score_judgments(tmp_path)
    metrics = output["modes"]["vector"]
    assert metrics["answer_correctness"]["rate"] == 1
    assert metrics["faithfulness"]["rate"] == 0.5
    assert metrics["unsupported_claim_rate"]["rate"] == 0.5
    assert metrics["correct_abstention"]["rate"] is None
    assert output["paired_correctness_by_category"]["lookup"] == dict(wins=0, ties=1, losses=0)


def test_unreviewed_scores_rejected(tmp_path):
    write_fixture(tmp_path, reviewer="")
    with pytest.raises(ValueError, match="reviewer"):
        score_judgments(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("supported_cited_claims", "2"),
        ("claims_with_supporting_citations", "2"),
    ],
)
def test_inconsistent_human_support_counts_rejected(tmp_path, field, value):
    write_fixture(tmp_path)
    path = tmp_path / "judgments.csv"
    with path.open() as file:
        rows = list(csv.DictReader(file))
    rows[0][field] = value
    with path.open("w") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="Inconsistent"):
        score_judgments(tmp_path)
