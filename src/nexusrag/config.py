from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://nexusrag:nexusrag-local-only@127.0.0.1:55433/nexusrag"
    )
    neo4j_uri: str = "bolt://127.0.0.1:57687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("nexusrag-local-only")
    openai_api_key: SecretStr = SecretStr("")
    disable_paid_api: bool = True
    generation_model: str = "gpt-5.4-mini-2026-03-17"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    corpus_dir: Path = Path("corpus")
    artifact_dir: Path = Path("artifacts")
    results_dir: Path = Path("results/runs")
    api_budget_usd: float = Field(default=50, gt=0, le=50)
    input_usd_per_million: float = Field(default=0.75, gt=0, allow_inf_nan=False)
    output_usd_per_million: float = Field(default=4.50, gt=0, allow_inf_nan=False)
    candidate_k: int = Field(default=20, ge=1, le=20)
    context_chunks: int = Field(default=8, ge=1, le=8)
    context_tokens: int = Field(default=3000, ge=1, le=3000)
    max_output_tokens: int = Field(default=1800, ge=1, le=4000)
    prompt_version: str = "grounded-v1"
    extraction_prompt_version: str = "ontology-v1"
    chunker_version: str = "markdown-lines-v1"
    graph_source: Literal["llm", "mermaid_fixture"] = "llm"

    def fingerprint(self) -> dict:
        return self.model_dump(
            mode="json",
            exclude={
                "database_url",
                "neo4j_password",
                "openai_api_key",
                "neo4j_uri",
                "neo4j_user",
            },
        )
