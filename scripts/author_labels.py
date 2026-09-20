"""Source-checked draft labels. This script never marks a label human-reviewed."""

import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
docs = {
    p.stem: p.read_text().splitlines(keepends=True) for p in (root / "corpus/docs").glob("*.md")
}


def span(doc, start, end=None):
    end = end or start
    return dict(
        document_id=doc,
        line_start=start,
        line_end=end,
        quote="".join(docs[doc][start - 1 : end]),
        relevance=2,
    )


def line_span(doc, text):
    matches = [i + 1 for i, line in enumerate(docs[doc]) if text in line]
    assert len(matches) == 1, (doc, text, matches)
    return span(doc, matches[0])


edges = {}

for i, line in enumerate(docs["architecture"]):
    match = re.fullmatch(r"([a-z][a-z-]*) -+>(?:\|[^|]+\|)? ([a-z][a-z-]*)\s*", line)
    if match:
        a, b = match.groups()
        edges[(a, b)] = span("architecture", i + 1)


def route(*nodes):
    return [edges[(a, b)] for a, b in zip(nodes, nodes[1:], strict=False)]


def rels(spans):
    result = []
    for s in spans:
        match = re.fullmatch(r"([a-z][a-z-]*) -+>(?:\|[^|]+\|)? ([a-z][a-z-]*)\s*", s["quote"])
        if not match:
            continue
        a, b = match.groups()
        if a == "queue":
            result.append((b, "CONSUMES_FROM", "kafka"))
        elif b == "queue":
            result.append((a, "PUBLISHES_TO", "kafka"))
        elif b in ["cache", "postgresql"]:
            result.append((a, "USES_STORE", b))
        else:
            result.append((a, "CALLS", b))
    return result


questions = [
    (
        "What is Checkout responsible for?",
        "Processes checkout orders, retrieving the cart and orchestrating payment, shipping and email notification.",
        [[span("checkout", 9, 10)], [line_span("services", "[checkout]")]],
        ["checkout"],
        None,
    ),
    (
        "Which language implements Cart?",
        "The overview identifies .NET; the Cart page supplies C# code (cs fences). Accept .NET/C# with this distinction.",
        [[line_span("services", "[cart]")]],
        ["cart"],
        None,
    ),
    (
        "What does Quote calculate?",
        "Shipping costs based on the number of items to ship.",
        [[span("quote", 8, 10)], [line_span("services", "[quote]")]],
        ["quote"],
        None,
    ),
    (
        "What does Recommendation do?",
        "Recommends products based on product IDs the user is browsing; overview describes recommendations based on the cart.",
        [[span("recommendation", 8, 9)], [line_span("services", "[recommendation]")]],
        ["recommendation"],
        None,
    ),
    (
        "What does Accounting process?",
        "Incoming orders; mock total sold-product amount calculation, prints received orders, and saves Kafka records to PostgreSQL.",
        [[span("accounting", 7, 9)], [line_span("services", "[accounting]")]],
        ["accounting"],
        None,
    ),
    (
        "Does the documented Frontend require login?",
        "No sign-up or login required; session IDs are generated automatically.",
        [[line_span("services", "[frontend]")]],
        ["frontend"],
        None,
    ),
    (
        "What is the default Kafka order topic?",
        "orders, configured by KAFKA_TOPIC.",
        [[line_span("kafka", "| `KAFKA_TOPIC`")]],
        ["kafka"],
        None,
    ),
    (
        "Which logging package does Checkout bridge to?",
        "slog, via the OpenTelemetry logging bridge.",
        [[line_span("checkout", "bridge to send its logs")]],
        ["checkout"],
        None,
    ),
    (
        "Which service does Shipping call for quotes?",
        "Quote via HTTP.",
        [route("shipping", "quote"), [span("quote", 8, 10)]],
        ["shipping", "quote"],
        "neighbors",
    ),
    (
        "Which catalog service does Recommendation call?",
        "Product Catalog.",
        [route("recommendation", "product-catalog")],
        ["product-catalog", "recommendation"],
        "neighbors",
    ),
    (
        "Which broker receives Checkout’s order messages?",
        "Kafka.",
        [route("checkout", "queue"), [line_span("kafka", "| `KAFKA_TOPIC`")]],
        ["checkout"],
        "neighbors",
    ),
    (
        "Which broker does Accounting consume from?",
        "Kafka.",
        [
            route("queue", "accounting"),
            [span("accounting", 7, 9)],
            [line_span("kafka", "| `KAFKA_TOPIC`")],
        ],
        ["accounting"],
        "neighbors",
    ),
    (
        "Which broker does Fraud Detection consume from?",
        "Kafka.",
        [route("queue", "fraud-detection"), [line_span("kafka", "| `KAFKA_TOPIC`")]],
        ["fraud-detection"],
        "neighbors",
    ),
    (
        "Which data store does Cart use?",
        "Valkey (cache).",
        [route("cart", "cache"), [span("cart", 7, 8)], [line_span("services", "[cart]")]],
        ["cart"],
        "neighbors",
    ),
    (
        "How does Checkout reach Quote through Shipping?",
        "Checkout CALLS Shipping; Shipping CALLS Quote.",
        [route("checkout", "shipping", "quote")],
        ["checkout", "shipping", "quote"],
        "paths",
    ),
    (
        "How does Frontend connect to Cart’s data store?",
        "Frontend CALLS Cart; Cart USES_STORE Valkey.",
        [route("frontend", "cart", "cache")],
        ["frontend", "cart"],
        "paths",
    ),
    (
        "How does Checkout connect to Cart’s data store?",
        "Checkout CALLS Cart; Cart USES_STORE Valkey.",
        [route("checkout", "cart", "cache")],
        ["checkout", "cart"],
        "paths",
    ),
    (
        "Trace Frontend’s catalog connection through Recommendation.",
        "Frontend CALLS Recommendation; Recommendation CALLS Product Catalog.",
        [route("frontend", "recommendation", "product-catalog")],
        ["frontend", "recommendation", "product-catalog"],
        "paths",
    ),
    (
        "What messaging path connects Checkout to Accounting?",
        "Checkout PUBLISHES_TO Kafka; Accounting CONSUMES_FROM Kafka.",
        [route("checkout", "queue", "accounting"), [line_span("kafka", "| `KAFKA_TOPIC`")]],
        ["checkout", "accounting"],
        "messaging",
    ),
    (
        "What messaging path connects Checkout to Fraud Detection?",
        "Checkout PUBLISHES_TO Kafka; Fraud Detection CONSUMES_FROM Kafka.",
        [route("checkout", "queue", "fraud-detection"), [line_span("kafka", "| `KAFKA_TOPIC`")]],
        ["checkout", "fraud-detection"],
        "messaging",
    ),
    (
        "Trace Frontend’s Payment connection through Checkout.",
        "Frontend CALLS Checkout; Checkout CALLS Payment.",
        [route("frontend", "checkout", "payment")],
        ["frontend", "checkout", "payment"],
        "paths",
    ),
    (
        "Trace Frontend’s Email connection through Checkout.",
        "Frontend CALLS Checkout; Checkout CALLS Email.",
        [route("frontend", "checkout", "email")],
        ["frontend", "checkout", "email"],
        "paths",
    ),
    (
        "Trace Frontend → Checkout → Shipping → Quote.",
        "Frontend CALLS Checkout; Checkout CALLS Shipping; Shipping CALLS Quote.",
        [route("frontend", "checkout", "shipping", "quote")],
        ["frontend", "checkout", "shipping", "quote"],
        "paths",
    ),
    (
        "Trace Frontend’s order flow through Checkout to Accounting.",
        "Frontend CALLS Checkout; Checkout PUBLISHES_TO Kafka; Accounting CONSUMES_FROM Kafka.",
        [route("frontend", "checkout", "queue", "accounting")],
        ["frontend", "checkout", "accounting"],
        "messaging",
    ),
    (
        "Trace Frontend’s order flow through Checkout to Fraud Detection.",
        "Frontend CALLS Checkout; Checkout PUBLISHES_TO Kafka; Fraud Detection CONSUMES_FROM Kafka.",
        [route("frontend", "checkout", "queue", "fraud-detection")],
        ["frontend", "checkout", "fraud-detection"],
        "messaging",
    ),
    (
        "Trace Frontend → Checkout → Cart → its data store.",
        "Frontend CALLS Checkout; Checkout CALLS Cart; Cart USES_STORE Valkey.",
        [route("frontend", "checkout", "cart", "cache")],
        ["frontend", "checkout", "cart"],
        "paths",
    ),
    (
        "Trace Checkout’s order flow through Accounting to its database.",
        "Checkout PUBLISHES_TO Kafka; Accounting CONSUMES_FROM Kafka; Accounting USES_STORE PostgreSQL.",
        [route("checkout", "queue", "accounting", "postgresql")],
        ["checkout", "accounting"],
        "messaging",
    ),
    (
        "Trace Frontend Proxy → Frontend → Shipping → Quote.",
        "Frontend Proxy CALLS Frontend; Frontend CALLS Shipping; Shipping CALLS Quote.",
        [route("frontend-proxy", "frontend", "shipping", "quote")],
        ["frontend-proxy", "frontend", "shipping", "quote"],
        "paths",
    ),
    (
        "Compare Checkout’s Shipping connection with its Accounting connection.",
        "Checkout calls Shipping over HTTP; Accounting receives orders asynchronously through Kafka, not a documented direct call.",
        [route("checkout", "shipping") + route("checkout", "queue", "accounting")],
        ["checkout", "shipping", "accounting"],
        None,
    ),
    (
        "Which documented services consume Checkout’s order messages, and how many?",
        "Accounting and Fraud Detection: two documented consumers through Kafka.",
        [
            route("checkout", "queue", "accounting") + route("queue", "fraud-detection"),
            [line_span("kafka", "| `KAFKA_TOPIC`")],
        ],
        ["checkout"],
        "messaging",
    ),
    (
        "Which direct service-call targets do Frontend and Checkout share?",
        "Cart, Currency, Shipping, and Product Catalog: four shared CALLS targets.",
        [
            [
                edges[(a, b)]
                for b in ["cart", "currency", "shipping", "product-catalog"]
                for a in ["frontend", "checkout"]
            ]
        ],
        ["frontend", "checkout"],
        "shared",
    ),
    (
        "Compare Frontend’s direct and Recommendation-mediated catalog paths.",
        "Frontend directly calls Product Catalog and also calls Recommendation, which calls Product Catalog.",
        [
            route("frontend", "product-catalog")
            + route("frontend", "recommendation", "product-catalog")
        ],
        ["frontend", "recommendation", "product-catalog"],
        None,
    ),
    (
        "What depends on the database?",
        "Clarify which database and which kind of dependency.",
        [],
        [],
        None,
    ),
    (
        "Is it safe to restart the queue?",
        "Clarify the environment and component. Static documentation cannot establish operational safety.",
        [],
        ["kafka"],
        None,
    ),
    (
        "Show what is upstream of Checkout.",
        "Clarify whether upstream means callers, call targets, producers, or consumers.",
        [],
        ["checkout"],
        None,
    ),
    (
        "Which version is running in our environment?",
        "The snapshot cannot identify a user environment. Ask for the component, environment and runtime evidence.",
        [],
        [],
        None,
    ),
    (
        "What was production Checkout P95 latency yesterday?",
        "Not supported: no production telemetry or dated latency measurements in the corpus.",
        [],
        ["checkout"],
        None,
    ),
    (
        "Which actual customers experienced failed payments?",
        "Not supported: no actual customer incident records.",
        [],
        [],
        None,
    ),
    (
        "How many production outages occurred last month?",
        "Not supported: no production incident history.",
        [],
        [],
        None,
    ),
    (
        "Will a Kafka outage definitely fail every checkout?",
        "Cannot determine from documentation; dependency edges do not prove outage propagation or universal failure.",
        [],
        ["kafka", "checkout"],
        None,
    ),
]
dev = {1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 23, 28, 33, 34, 35, 40}
rows = []
for i, (q, gold, sets, entities, template) in enumerate(questions, 1):
    category = (
        "lookup"
        if i <= 8
        else "single_hop"
        if i <= 14
        else "two_hop"
        if i <= 22
        else "three_hop"
        if i <= 28
        else "comparison"
        if i in [29, 32]
        else "aggregation"
        if i in [30, 31]
        else "ambiguous"
        if i <= 36
        else "no_answer"
        if i <= 39
        else "unsupported_inference"
    )
    group = (
        "shipping_quote_routes"
        if i in [9, 15, 23, 28]
        else "messaging_routes"
        if i in [11, 12, 13, 19, 20, 24, 25, 27, 29, 30]
        else "cart_storage_routes"
        if i in [14, 16, 17, 26]
        else "catalog_routes"
        if i in [10, 18, 32]
        else f"q{i:02}"
    )
    behavior = (
        "answered" if i <= 32 else "clarification_needed" if i <= 36 else "insufficient_evidence"
    )
    rows.append(
        dict(
            id=f"{i:02}",
            split="dev" if i in dev else "test",
            group=group,
            category=category,
            question=q,
            expected_behavior=behavior,
            gold_answer=gold,
            required_relationships=rels(sets[0]) if sets else [],
            evidence_sets=sets,
            overview_answers=any(
                all(s["document_id"] in ["architecture", "services"] for s in support)
                for support in sets
            ),
            constrained_path=i in range(15, 29) or i == 32,
            gold_entities=entities,
            gold_template=template,
            review_status="source_checked_by_agent",
            reviewer=None,
            notes="Draft source labels checked against frozen Markdown; independent human review is pending.",
        )
    )
(root / "evaluation/questions.jsonl").write_text(
    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
)
print("Wrote 40 draft labels, 16 development / 24 test; no human-review claim.")
