from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from nexusrag.config import Settings
from nexusrag.generation.llm import LLM, strict_schema
from nexusrag.models import Answer, Extraction


def test_strict_schema_has_required_nullable_confidence():
    schema = strict_schema(Extraction.model_json_schema())
    raw = schema["$defs"]["RawAssertion"]
    assert raw["additionalProperties"] is False
    assert "confidence_uncalibrated" in raw["required"]
    assert "default" not in raw["properties"]["confidence_uncalibrated"]


def test_provider_configuration_usage_and_malformed_output_accounting(tmp_path, monkeypatch):
    captured = {}

    class Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                model="actual-model",
                usage=SimpleNamespace(input_tokens=100, output_tokens=30),
                status="completed",
                output_text="malformed",
            )

    monkeypatch.setattr(
        "nexusrag.generation.llm.OpenAI", lambda **kwargs: SimpleNamespace(responses=Responses())
    )
    monkeypatch.setattr("nexusrag.generation.llm.token_count", len)
    settings = Settings(
        openai_api_key=SecretStr("test-only"), artifact_dir=tmp_path, disable_paid_api=False
    )
    llm = LLM(settings)
    with pytest.raises(ValueError):
        llm.generate(Answer, "Instructions", {"question": "Question"})
    assert captured["reasoning"] == {"effort": "none"}
    assert captured["store"] is False
    assert llm.calls[0]["actual_model"] == "actual-model"
    assert llm.calls[0]["input_tokens"] == 100
    assert llm.calls[0]["estimated_cost_usd"] == pytest.approx(0.00021)
    assert "test-only" not in str(llm.calls)


def test_missing_key_fails_before_reserving_budget(tmp_path):
    llm = LLM(Settings(openai_api_key=SecretStr(""), artifact_dir=tmp_path, disable_paid_api=False))
    with pytest.raises(RuntimeError, match="api_key_missing"):
        llm.generate(Answer, "Instructions", {})
    assert not (tmp_path / "spend.sqlite").exists()
