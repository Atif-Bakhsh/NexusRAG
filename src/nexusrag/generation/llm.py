import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import TypeVar

import tiktoken
from openai import OpenAI
from pydantic import BaseModel

from nexusrag.config import Settings

T = TypeVar("T", bound=BaseModel)


def token_count(text: str) -> int:
    return len(tiktoken.get_encoding("o200k_base").encode(text))


def strict_schema(schema: dict) -> dict:
    """The structured-output subset requires every object field and no extra keys."""
    if isinstance(schema, dict):
        schema.pop("default", None)
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            schema["required"] = list(schema.get("properties", {}))
        for value in schema.values():
            if isinstance(value, dict):
                strict_schema(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        strict_schema(item)
    return schema


class Budget:
    """Atomic local spend reservations. Unknown usage keeps its conservative reservation."""

    def __init__(self, path: Path, limit: float):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.limit = path, limit
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS spend (id TEXT PRIMARY KEY, amount REAL, status TEXT)"
            )

    def reserve(self, amount: float) -> str:
        with sqlite3.connect(self.path, timeout=10) as conn:
            conn.execute("BEGIN IMMEDIATE")
            spent = conn.execute("SELECT COALESCE(SUM(amount),0) FROM spend").fetchone()[0]
            if spent + amount > self.limit:
                raise RuntimeError("application_budget_exhausted")
            id_ = str(uuid.uuid4())
            conn.execute("INSERT INTO spend VALUES (?, ?, 'reserved')", (id_, amount))
        return id_

    def settle(self, id_: str, amount: float):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE spend SET amount=?,status='measured' WHERE id=?", (amount, id_))


class LLM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.calls: list[dict] = []

    def generate(
        self, schema: type[T], instructions: str, payload: dict, max_output: int | None = None
    ) -> T:
        if not self.settings.openai_api_key.get_secret_value():
            raise RuntimeError("openai_api_key_missing")
        output_limit = max_output or self.settings.max_output_tokens
        json_schema = strict_schema(schema.model_json_schema())
        content = json.dumps(payload, ensure_ascii=False)
        estimate_input = token_count(instructions + content + json.dumps(json_schema)) + 512
        budget = Budget(self.settings.artifact_dir / "spend.sqlite", self.settings.api_budget_usd)
        reservation = budget.reserve(
            (
                estimate_input * self.settings.input_usd_per_million
                + output_limit * self.settings.output_usd_per_million
            )
            / 1e6
        )
        started = time.perf_counter()
        record: dict = {
            "requested_model": self.settings.generation_model,
            "status": "failed",
            "reservation_id": reservation,
            "input_tokens": None,
            "output_tokens": None,
            "estimated_cost_usd": None,
        }
        self.calls.append(record)
        try:
            client = OpenAI(
                api_key=self.settings.openai_api_key.get_secret_value(), timeout=45, max_retries=0
            )
            response = client.responses.create(
                model=self.settings.generation_model,
                reasoning={"effort": "none"},
                instructions=instructions,
                input=content,
                max_output_tokens=output_limit,
                store=False,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema.__name__,
                        "schema": json_schema,
                        "strict": True,
                    }
                },
            )
            record["actual_model"] = response.model
            if response.usage:
                usage = response.usage
                cost = (
                    usage.input_tokens * self.settings.input_usd_per_million
                    + usage.output_tokens * self.settings.output_usd_per_million
                ) / 1e6
                record.update(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    estimated_cost_usd=cost,
                )
                budget.settle(reservation, cost)
            if response.status != "completed":
                raise ValueError("model_output_incomplete")
            parsed = schema.model_validate_json(response.output_text)
            record["status"] = "completed"
            return parsed
        finally:
            record["latency_ms"] = (time.perf_counter() - started) * 1000
