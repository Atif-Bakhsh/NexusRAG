from types import SimpleNamespace

import pytest
from pydantic import SecretStr, ValidationError

from nexusrag.config import Settings
from nexusrag.generation.llm import LLM
from nexusrag.models import Answer


@pytest.mark.parametrize(
    "name,value",
    [
        ("candidate_k", 21),
        ("candidate_k", 0),
        ("context_chunks", 9),
        ("context_tokens", 3001),
        ("max_output_tokens", 0),
        ("api_budget_usd", 51),
        ("input_usd_per_million", -1),
        ("output_usd_per_million", float("nan")),
    ],
)
def test_configuration_enforces_experiment_bounds(name, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{name: value})


def test_paid_disable_precedes_provider_and_spend_ledger(tmp_path):
    llm = LLM(
        Settings(disable_paid_api=True, openai_api_key=SecretStr("test-key"), artifact_dir=tmp_path)
    )
    with pytest.raises(RuntimeError, match="paid_api_disabled"):
        llm.generate(Answer, "ignored", {})
    assert not list(tmp_path.iterdir()) and not llm.calls


def test_configuration_fingerprint_never_contains_credentials():
    settings = Settings(
        openai_api_key=SecretStr("private-api-key"),
        database_url=SecretStr("private-database-url"),
        neo4j_password=SecretStr("private-password"),
    )
    assert "private-" not in str(settings.fingerprint())


def test_preflight_reports_independent_failures_without_leaking_secrets(monkeypatch):
    from nexusrag.preflight import run

    def fail(*args, **kwargs):
        raise RuntimeError("secret-password-in-connection-string")

    monkeypatch.setattr("nexusrag.preflight.Repository", fail)
    monkeypatch.setattr(
        "nexusrag.preflight.GraphStore", lambda s: SimpleNamespace(ping=fail, close=lambda: None)
    )
    monkeypatch.setattr("nexusrag.preflight.Embedder", fail)
    result = run(Settings(disable_paid_api=True), require_ready=True, require_generation=True)
    assert result["status"] == "failed" and result["paid_calls"] == 0
    by_name = {c["check"]: c for c in result["checks"]}
    assert by_name["corpus"]["status"] == "pass"
    for name in ("postgresql", "neo4j", "embedding_model", "generation"):
        assert by_name[name]["status"] == "fail"
    assert "secret-password" not in str(result)


def test_cli_invalid_environment_does_not_echo_value(monkeypatch, capsys):
    from nexusrag.cli import main

    monkeypatch.setenv("API_BUDGET_USD", "secret-invalid-value")
    monkeypatch.setattr("sys.argv", ["nexusrag", "preflight"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "secret-invalid" not in capsys.readouterr().out
