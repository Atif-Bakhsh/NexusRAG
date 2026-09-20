import re

from nexusrag.graph.ontology import Registry, normalize
from nexusrag.models import Plan


def plan_question(question: str, registry: Registry) -> Plan:
    q = normalize(question)
    entities = registry.matches(question)
    if "through" in q:
        before, after = q.split("through", 1)
        sources, via = registry.matches(before), registry.matches(after)
        if len(sources) >= 2 and via:
            entities = list(dict.fromkeys(sources[:1] + via + sources[1:]))
    base = Plan(matched_entities=entities)
    if re.search(r"\b(upstream|downstream)\b", q):
        return base.model_copy(
            update={
                "clarification": "Do you mean callers, call targets, message producers, or consumers?"
            }
        )
    if re.search(r"\b(database|queue)\b", q) and not entities:
        return base.model_copy(
            update={"clarification": "Which named data store or broker do you mean?"}
        )
    if "safe to restart" in q:
        return base.model_copy(
            update={
                "clarification": "Which component and environment? Documentation alone cannot establish restart safety."
            }
        )
    if not entities:
        return base.model_copy(update={"fallback_reason": "no_entity_match"})
    if q.startswith("compare"):
        return base.model_copy(update={"fallback_reason": "comparison_uses_vector_evidence"})
    if any(x in q for x in ["share", "common", "both"]) and len(entities) == 2:
        return base.model_copy(update={"template_id": "shared"})
    if any(x in q for x in ["message", "messaging", "order flow", "consume", "broker"]):
        if len(entities) == 1 and any(x in q for x in ["consume from", "broker does"]):
            return base.model_copy(update={"template_id": "neighbors"})
        return base.model_copy(update={"template_id": "messaging"})
    if any(x in q for x in ["path", "through", "connect", "trace", "reach", "depend", "caller"]):
        reverse = any(x in q for x in ["callers", "calls to", "depends on", "depend on"])
        return base.model_copy(update={"template_id": "paths", "reverse": reverse})
    if any(x in q for x in ["call", "store", "use", "publish"]):
        return base.model_copy(update={"template_id": "neighbors"})
    return base.model_copy(update={"fallback_reason": "unsupported_question_shape"})
