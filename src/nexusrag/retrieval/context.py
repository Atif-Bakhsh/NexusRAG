import json
from collections.abc import Callable

from nexusrag.models import Chunk, GraphPath


def evidence_payload(chunk: Chunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "title": chunk.title,
        "section": chunk.section,
        "text": chunk.text,
    }


def context_text(chunks) -> str:
    return json.dumps([evidence_payload(c) for c in chunks], ensure_ascii=False)


def select_context(
    candidates: list[Chunk],
    paths: list[GraphPath],
    available: dict[str, Chunk],
    count: Callable[[str], int],
    max_chunks: int = 8,
    max_tokens: int = 3000,
    document_filter: list[str] | None = None,
) -> tuple[list[Chunk], list[GraphPath], list[str]]:
    selected: dict[str, Chunk] = {}
    selected_paths: list[GraphPath] = []
    dropped: list[str] = []

    def fits(chunks: list[Chunk]) -> bool:
        merged = {**selected, **{c.chunk_id: c for c in chunks}}
        return len(merged) <= max_chunks and count(context_text(merged.values())) <= max_tokens

    for path in paths:
        if len(selected_paths) == 2:
            dropped.append("path_selection_limit")
            continue
        bundle = [available[id_] for id_ in path.chunk_ids if id_ in available]
        if len(bundle) != len(path.chunk_ids) or not bundle:
            dropped.append("missing_path_evidence")
            continue
        if any(
            a.corpus_version != available[e.chunk_id].corpus_version
            or e.quote not in available[e.chunk_id].text
            for a in path.assertions
            for e in a.evidence
        ):
            dropped.append("invalid_path_provenance")
            continue
        if document_filter is not None and any(
            c.document_id not in document_filter for c in bundle
        ):
            dropped.append("document_filter")
            continue
        if not fits(bundle):
            dropped.append("path_bundle_exceeds_budget")
            continue
        selected.update({c.chunk_id: c for c in bundle})
        selected_paths.append(path)
    for chunk in candidates:
        if chunk.chunk_id not in selected and fits([chunk]):
            selected[chunk.chunk_id] = chunk
    return list(selected.values()), selected_paths, dropped
