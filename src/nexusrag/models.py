from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EntityType = Literal["Service", "DataStore", "MessageBroker"]
Predicate = Literal["CALLS", "USES_STORE", "PUBLISHES_TO", "CONSUMES_FROM"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Document(StrictModel):
    document_id: str
    path: str
    repository_path: str
    source_url: str
    sha256: str


class Manifest(StrictModel):
    corpus_version: str
    repository_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    repository: str
    license: str
    attribution: str
    modification_notice: str
    documents: list[Document]


class Chunk(StrictModel):
    chunk_id: str
    corpus_version: str
    document_id: str
    title: str
    source_url: str
    section: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    text: str
    content_hash: str
    document_date: str | None = None
    page_number: None = None

    @property
    def embedding_text(self) -> str:
        return f"{self.title} / {self.section}\n{self.text}"


class Mention(StrictModel):
    chunk_id: str
    quote: str = Field(min_length=1)


class Entity(StrictModel):
    entity_id: str
    name: str
    entity_type: EntityType
    aliases: list[str]
    mentions: list[Mention]
    resolution_method: str = "versioned_alias_map"
    review_status: Literal["unreviewed", "reviewed"] = "unreviewed"


class RawAssertion(StrictModel):
    subject: str
    predicate: Predicate
    object: str
    evidence: list[Mention] = Field(min_length=1)
    confidence_uncalibrated: float | None = Field(default=None, ge=0, le=1)


class Extraction(StrictModel):
    assertions: list[RawAssertion]


class Assertion(RawAssertion):
    assertion_id: str
    corpus_version: str
    extraction_model: str
    prompt_version: str
    validation_status: Literal["validated"] = "validated"
    review_status: Literal["unreviewed", "reviewed"] = "unreviewed"


class GraphPath(StrictModel):
    nodes: list[str]
    assertions: list[Assertion]

    @property
    def chunk_ids(self) -> list[str]:
        return list(dict.fromkeys(e.chunk_id for a in self.assertions for e in a.evidence))


class Plan(StrictModel):
    template_id: Literal["neighbors", "paths", "messaging", "shared"] | None = None
    matched_entities: list[str] = Field(default_factory=list)
    match_method: str = "normalized_alias_boundary"
    reverse: bool = False
    fallback_reason: str | None = None
    clarification: str | None = None


class Statement(StrictModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class Answer(StrictModel):
    status: Literal["answered", "insufficient_evidence", "clarification_needed"]
    statements: list[Statement]
    limitations: list[str]

    @model_validator(mode="after")
    def answered_has_statements(self):
        if self.status == "answered" and not self.statements:
            raise ValueError("An answered response must contain cited statements")
        if self.status != "answered" and self.statements:
            raise ValueError("Abstentions must not contain factual answer statements")
        return self


class AskRequest(StrictModel):
    question: str = Field(min_length=3, max_length=2000)
    mode: Literal["vector", "graph_vector"] = "vector"
    document_filter: list[str] | None = Field(default=None, max_length=12)

    @model_validator(mode="after")
    def nonblank(self):
        self.question = self.question.strip()
        if len(self.question) < 3:
            raise ValueError("Question is blank or too short")
        return self
