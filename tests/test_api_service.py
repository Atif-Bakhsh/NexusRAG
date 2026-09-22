from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from nexusrag.api.app import app
from nexusrag.config import Settings
from nexusrag.graph.ontology import Registry
from nexusrag.models import Answer, AskRequest, Statement
from nexusrag.service import QueryService


@pytest.fixture
def fake_service(make_chunk, monkeypatch):
    c = make_chunk()
    records = {}

    class Repo:
        def active(self):
            return SimpleNamespace(
                version="v1", manifest={"documents": [{"document_id": "architecture"}]}
            )

        def ping(self):
            pass

        def search(self, *args):
            return [(c, 0.9)]

        def chunks(self, *args):
            return [c]

        def save_query(self, result):
            records[result["query_id"]] = result

        def get_query(self, id_):
            if id_ not in records:
                raise LookupError(id_)
            return records[id_]

    class Graph:
        def ping(self):
            pass

        def ready(self, *args):
            return True

        def retrieve(self, *args):
            raise TimeoutError("must not expose credentials or this text")

    monkeypatch.setattr("nexusrag.service.token_count", len)
    svc = QueryService(
        Settings(), Repo(), SimpleNamespace(query=lambda q: [1.0] * 384), Graph(), Registry()
    )
    monkeypatch.setattr("nexusrag.api.app.service", lambda: svc)
    return svc, records


class GoodLLM:
    calls = []

    def generate(self, *args, **kwargs):
        return Answer(
            status="answered",
            statements=[Statement(text="Checkout calls Shipping.", evidence_ids=["c1"])],
            limitations=[],
        )


def test_graph_failure_recorded_and_vector_fallback(fake_service):
    svc, records = fake_service
    result = svc.ask(
        AskRequest(question="Who does Checkout call?", mode="graph_vector"), llm=GoodLLM()
    )
    assert result["status"] == "completed"
    assert "graph_failed_using_vector" in result["trace"]["fallbacks"]
    assert result["trace"]["errors"] == [{"stage": "graph", "type": "TimeoutError"}]
    assert result["query_id"] in records


def test_provider_timeout_does_not_repair_or_fabricate(fake_service):
    class TimedOut:
        calls = []

        def generate(self, *args, **kwargs):
            raise TimeoutError("secret key must not be echoed")

    result = fake_service[0].ask(AskRequest(question="What is Checkout?"), llm=TimedOut())
    assert result["status"] == "failed" and result["answer"] is None
    assert "secret" not in str(result)


def test_ambiguous_question_requests_clarification_without_llm(fake_service):
    result = fake_service[0].ask(
        AskRequest(question="What is upstream of Checkout?", mode="graph_vector"), llm=GoodLLM()
    )
    assert result["answer"]["status"] == "clarification_needed"


def test_api_validation_liveness_records_and_ready(fake_service):
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 200
    assert client.post("/ask", json={"question": "   ", "mode": "vector"}).status_code == 422
    assert client.post("/ask", json={"question": "Hello?", "mode": "cypher"}).status_code == 422
    assert client.post("/ask", json={"question": "x" * 2001}).status_code == 422
    assert client.get("/queries/missing").status_code == 404
    record = fake_service[0].ask(AskRequest(question="What is Checkout?"), llm=GoodLLM())
    assert client.get(f"/queries/{record['query_id']}/trace").status_code == 200


def test_unknown_document_filter_rejected(fake_service):
    with pytest.raises(ValueError):
        fake_service[0].ask(
            AskRequest(question="What is Checkout?", document_filter=["unknown"]), llm=GoodLLM()
        )


def test_evaluation_corpus_change_aborts_before_retrieval(fake_service):
    svc, records = fake_service
    with pytest.raises(RuntimeError, match="corpus changed"):
        svc.ask(
            AskRequest(question="What is Checkout?"),
            generate=False,
            expected_corpus_version="different-version",
        )
    assert not records


def test_api_paid_disabled_returns_failure_record_and_releases_lock(fake_service):
    svc, records = fake_service
    svc.settings.disable_paid_api = True
    client = TestClient(app)
    for _ in range(2):
        response = client.post("/ask", json={"question": "What is Checkout?"})
        assert response.status_code == 502
        query_id = response.json()["detail"]["query_id"]
        assert records[query_id]["trace"]["calls"] == []
        assert client.get(f"/queries/{query_id}").status_code == 200
    assert not client.get("/ready").json()["generation_configured"]


def test_api_busy_and_unready_fail_explicitly(fake_service, monkeypatch):
    from nexusrag.api.app import query_lock

    client = TestClient(app)
    with query_lock:
        assert client.post("/ask", json={"question": "What is Checkout?"}).status_code == 429

    def unavailable():
        raise LookupError("private internal message")

    monkeypatch.setattr(fake_service[0].repository, "active", unavailable)
    assert client.get("/ready").status_code == 503
    response = client.post("/ask", json={"question": "What is Checkout?"})
    assert response.status_code == 503 and "private" not in response.text
