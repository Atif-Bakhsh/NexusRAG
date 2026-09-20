import json
import re
from pathlib import Path

from nexusrag.ingestion.corpus import digest
from nexusrag.models import Assertion, Chunk, Entity, Extraction

ENDPOINTS = {
    "CALLS": ("Service", "Service"),
    "USES_STORE": ("Service", "DataStore"),
    "PUBLISHES_TO": ("Service", "MessageBroker"),
    "CONSUMES_FROM": ("Service", "MessageBroker"),
}


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


class Registry:
    def __init__(self, path: Path = Path("corpus/aliases.json")):
        data = json.loads(path.read_text())
        self.version = data["version"]
        self.entities = {e.entity_id: e for e in map(Entity.model_validate, data["entities"])}
        self.aliases: dict[str, str] = {}
        for entity in self.entities.values():
            for alias in [entity.entity_id, entity.name, *entity.aliases]:
                key = normalize(alias)
                if key in self.aliases and self.aliases[key] != entity.entity_id:
                    raise ValueError(f"Alias collision: {key}")
                self.aliases[key] = entity.entity_id

    def resolve(self, name: str) -> str:
        key = normalize(name)
        if key not in self.aliases:
            raise ValueError(f"Unknown entity: {name}")
        return self.aliases[key]

    def matches(self, question: str) -> list[str]:
        normalized = normalize(question)
        candidates = []
        for alias, eid in self.aliases.items():
            for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", normalized):
                candidates.append((match.start(), match.end(), eid))
        # Prefer longest matching phrase: Frontend Proxy must not also match Frontend.
        accepted: list[tuple[int, int, str]] = []
        for start, end, eid in sorted(candidates, key=lambda m: (-(m[1] - m[0]), m[0])):
            if not any(start < b and end > a for a, b, _ in accepted):
                accepted.append((start, end, eid))
        return list(dict.fromkeys(eid for _, _, eid in sorted(accepted)))


def validate_extraction(
    extraction: Extraction,
    chunks: dict[str, Chunk],
    registry: Registry,
    corpus_version: str,
    model: str,
    prompt_version: str,
) -> list[Assertion]:
    assertions = []
    for raw in extraction.assertions:
        subject, object_ = registry.resolve(raw.subject), registry.resolve(raw.object)
        actual = (registry.entities[subject].entity_type, registry.entities[object_].entity_type)
        if actual != ENDPOINTS[raw.predicate] or subject == object_:
            raise ValueError("Invalid relationship endpoints")
        for evidence in raw.evidence:
            chunk = chunks.get(evidence.chunk_id)
            if chunk is None or chunk.corpus_version != corpus_version:
                raise ValueError("Evidence chunk missing or outside corpus")
            if evidence.quote not in chunk.text:
                raise ValueError("Evidence quote is not an exact source excerpt")
        key = json.dumps(
            [
                corpus_version,
                subject,
                raw.predicate,
                object_,
                sorted((e.chunk_id, e.quote) for e in raw.evidence),
            ]
        )
        assertions.append(
            Assertion(
                **raw.model_dump(exclude={"subject", "object"}),
                subject=subject,
                object=object_,
                assertion_id=digest(key)[:32],
                corpus_version=corpus_version,
                extraction_model=model,
                prompt_version=prompt_version,
            )
        )
    return assertions
