from typing import Literal

from pydantic import Field

from nexusrag.models import StrictModel


class SourceSpan(StrictModel):
    document_id: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str
    relevance: int = Field(default=2, ge=1, le=3)


class Question(StrictModel):
    id: str
    split: Literal["dev", "test"]
    group: str
    category: str
    question: str
    expected_behavior: Literal["answered", "insufficient_evidence", "clarification_needed"]
    gold_answer: str
    required_relationships: list[tuple[str, str, str]]
    evidence_sets: list[list[SourceSpan]]
    overview_answers: bool
    constrained_path: bool
    gold_entities: list[str]
    gold_template: Literal["neighbors", "paths", "messaging", "shared"] | None
    review_status: Literal["source_checked_by_agent", "human_reviewed"]
    reviewer: str | None = None
    notes: str = ""
