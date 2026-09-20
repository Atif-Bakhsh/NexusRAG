import json

import pytest
from pydantic import ValidationError

from nexusrag.graph.ontology import Registry, validate_extraction
from nexusrag.graph.planner import plan_question
from nexusrag.models import Extraction, Mention, RawAssertion


def test_entity_boundaries_and_longest_alias():
    r = Registry()
    assert r.matches("Frontend Proxy calls Frontend") == ["frontend-proxy", "frontend"]
    assert r.matches("cartography and paymentless") == []
    assert r.resolve("fraud_detection") == "fraud-detection"


def test_alias_collision_is_rejected(tmp_path):
    data = json.loads(open("corpus/aliases.json").read())
    data["entities"][0]["aliases"].append("cart")
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="collision"):
        Registry(path)


@pytest.mark.parametrize(
    "subject,predicate,object_,chunk,quote",
    [
        ("checkout", "USES_STORE", "shipping", "c1", "checkout --> shipping\n"),
        ("checkout", "CALLS", "shipping", "invented", "checkout --> shipping\n"),
        ("checkout", "CALLS", "shipping", "c1", "invented quote"),
        ("invented", "CALLS", "shipping", "c1", "checkout --> shipping\n"),
    ],
)
def test_assertion_validation_rejects_invalid_sources_and_types(
    make_chunk, subject, predicate, object_, chunk, quote
):
    raw = RawAssertion(
        subject=subject,
        predicate=predicate,
        object=object_,
        evidence=[Mention(chunk_id=chunk, quote=quote)],
    )
    with pytest.raises(ValueError):
        validate_extraction(
            Extraction(assertions=[raw]), {"c1": make_chunk()}, Registry(), "v1", "test", "test"
        )


def test_unknown_relationship_rejected():
    with pytest.raises(ValidationError):
        RawAssertion(subject="cart", predicate="DEPENDS_ON", object="cache", evidence=[])


def test_valid_quote_is_provenance_not_entailment(make_chunk):
    # Deliberately wrong semantic edge with a real quote passes structural checks.
    raw = RawAssertion(
        subject="shipping",
        predicate="CALLS",
        object="checkout",
        evidence=[Mention(chunk_id="c1", quote="checkout --> shipping\n")],
    )
    assert validate_extraction(
        Extraction(assertions=[raw]), {"c1": make_chunk()}, Registry(), "v1", "test", "test"
    )


def test_planner_route_order_reverse_clarification_and_fallback():
    r = Registry()
    p = plan_question("How does Checkout reach Quote through Shipping?", r)
    assert p.template_id == "paths"
    assert p.matched_entities == ["checkout", "shipping", "quote"]
    assert plan_question("Who depends on Cart?", r).reverse
    assert plan_question("Show upstream of Checkout", r).clarification
    assert plan_question("What does unknown do?", r).fallback_reason == "no_entity_match"
    assert plan_question("Which targets do Frontend and Checkout share?", r).template_id == "shared"
