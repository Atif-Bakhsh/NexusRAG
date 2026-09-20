"""Diagnostic fixture derived from the first explicit service diagram, never LLM results."""

import re

from nexusrag.graph.ontology import Registry, validate_extraction
from nexusrag.models import Chunk, Extraction, Mention, Predicate, RawAssertion


def diagram_assertions(chunks: list[Chunk], registry: Registry, version: str):
    assertions = []
    for chunk in chunks:
        if chunk.document_id != "architecture":
            continue
        for line in chunk.text.splitlines(keepends=True):
            match = re.fullmatch(r"([a-z][a-z-]*) -+>(?:\|[^|]+\|)? ([a-z][a-z-]*)\s*", line)
            if not match:
                continue
            subject, object_ = match.groups()
            try:
                subject, object_ = registry.resolve(subject), registry.resolve(object_)
            except ValueError:
                continue
            predicate: Predicate
            s, o = registry.entities[subject], registry.entities[object_]
            if s.entity_type == "MessageBroker":
                predicate, subject, object_ = "CONSUMES_FROM", object_, subject
            elif o.entity_type == "MessageBroker":
                predicate = "PUBLISHES_TO"
            elif o.entity_type == "DataStore":
                predicate = "USES_STORE"
            else:
                predicate = "CALLS"
            raw = RawAssertion(
                subject=subject,
                predicate=predicate,
                object=object_,
                evidence=[Mention(chunk_id=chunk.chunk_id, quote=line)],
            )
            assertions.extend(
                validate_extraction(
                    Extraction(assertions=[raw]),
                    {chunk.chunk_id: chunk},
                    registry,
                    version,
                    "deterministic-mermaid-fixture",
                    "fixture-v1",
                )
            )
    # Overlapping chunks may repeat an edge. Retain one reproducible support per edge.
    return list({(a.subject, a.predicate, a.object): a for a in reversed(assertions)}.values())
