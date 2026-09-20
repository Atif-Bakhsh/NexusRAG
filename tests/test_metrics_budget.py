import pytest

from nexusrag.evaluation.metrics import distribution, ranking_metrics
from nexusrag.generation.llm import Budget


def test_ranked_metrics_alternative_support_and_deduplication():
    relevance = {"a": 2, "b": 2, "c": 1}
    supports = [[{"a"}, {"b"}], [{"c"}]]
    m = ranking_metrics(["x", "a", "a", "b"], relevance, supports, 3)
    assert m["complete_evidence"] and m["recall"] == pytest.approx(2 / 3)
    assert m["precision"] == pytest.approx(2 / 3) and m["mrr"] == 0.5
    assert not ranking_metrics(["a"], relevance, supports, 3)["complete_evidence"]
    assert ranking_metrics(["c"], relevance, supports, 3)["complete_evidence"]
    assert 0 < m["ndcg"] < 1


def test_no_answer_recall_is_undefined():
    assert ranking_metrics(["a"], {}, [], 20)["recall"] is None
    assert distribution([1, 2, 3, 4])["p95"] == 4


def test_budget_reservations_enforce_limit_across_instances(tmp_path):
    path = tmp_path / "spend.sqlite"
    b = Budget(path, 1)
    reservation = b.reserve(0.6)
    with pytest.raises(RuntimeError, match="budget"):
        Budget(path, 1).reserve(0.5)
    b.settle(reservation, 0.1)
    Budget(path, 1).reserve(0.5)
