import math
from statistics import median

from nexusrag.evaluation.schema import Question
from nexusrag.models import Chunk


def map_gold(
    question: Question, chunks: list[Chunk]
) -> tuple[dict[str, int], list[list[set[str]]]]:
    """Each support set contains spans; each span may map to multiple covering chunks.

    Overlap alone is not support: the full labeled span must be present in one chunk.
    Long spans should be labeled as separate minimal source spans.
    """
    relevance: dict[str, int] = {}
    alternatives = []
    for spans in question.evidence_sets:
        required = []
        for span in spans:
            covering = {
                c.chunk_id
                for c in chunks
                if c.document_id == span.document_id
                and c.line_start <= span.line_start
                and c.line_end >= span.line_end
                and span.quote in c.text
            }
            for id_ in covering:
                relevance[id_] = max(relevance.get(id_, 0), span.relevance)
            required.append(covering)
        alternatives.append(required)
    return relevance, alternatives


def ranking_metrics(
    ids: list[str], relevance: dict[str, int], support_sets: list[list[set[str]]], k: int
) -> dict:
    ranked = list(dict.fromkeys(ids))[:k]
    if not support_sets:
        return dict(
            recall=None,
            precision=None,
            mrr=None,
            ndcg=None,
            complete_evidence=None,
            retrieved_count=len(ranked),
        )
    hits = [int(id_ in relevance) for id_ in ranked]
    dcg = sum((2 ** relevance.get(id_, 0) - 1) / math.log2(i + 2) for i, id_ in enumerate(ranked))
    ideal = sum(
        (2**grade - 1) / math.log2(i + 2)
        for i, grade in enumerate(sorted(relevance.values(), reverse=True)[:k])
    )
    return {
        "recall": sum(hits) / len(relevance) if relevance else 0.0,
        "precision": sum(hits) / len(ranked) if ranked else 0.0,
        "mrr": next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0.0),
        "ndcg": dcg / ideal if ideal else 0.0,
        "complete_evidence": any(
            bool(spans) and all(bool(cover & set(ranked)) for cover in spans)
            for spans in support_sets
        ),
        "retrieved_count": len(ranked),
    }


def distribution(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": None, "p95": None}
    ordered = sorted(values)
    return {
        "n": len(values),
        "median": median(values),
        "p95": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "p95_method": "nearest_rank",
    }
