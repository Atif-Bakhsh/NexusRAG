import pytest

from nexusrag.generation.answers import answer_question, validate_answer
from nexusrag.models import Answer, GraphPath, Statement
from nexusrag.retrieval.context import select_context


def test_complete_path_bundle_or_nothing(make_chunk, make_assertion):
    c1 = make_chunk()
    c2 = make_chunk("c2", "shipping --> quote\n")
    path = GraphPath(
        nodes=["checkout", "shipping", "quote"],
        assertions=[
            make_assertion(),
            make_assertion(
                subject="shipping", object_="quote", chunk="c2", quote=c2.text, id_="a2"
            ),
        ],
    )
    context, paths, dropped = select_context([c1], [path], {"c1": c1, "c2": c2}, len, max_chunks=1)
    assert not paths and dropped == ["path_bundle_exceeds_budget"]
    assert context == [c1]
    context, paths, _ = select_context([c1, c2], [path], {"c1": c1, "c2": c2}, len, max_chunks=2)
    assert len(context) == 2 and paths == [path]


def test_path_missing_evidence_or_document_filter_is_dropped(make_chunk, make_assertion):
    c = make_chunk()
    p = GraphPath(nodes=["checkout", "shipping"], assertions=[make_assertion()])
    assert select_context([], [p], {}, len)[1] == []
    assert select_context([], [p], {"c1": c}, len, document_filter=["cart"])[1] == []


def test_citation_ids_and_corpus_validated(make_chunk):
    answer = Answer(
        status="answered",
        statements=[Statement(text="Calls Shipping", evidence_ids=["invented"])],
        limitations=[],
    )
    with pytest.raises(ValueError, match="citation"):
        validate_answer(answer, [make_chunk()], "v1")
    answer.statements[0].evidence_ids = ["c1"]
    with pytest.raises(ValueError, match="Mixed corpus"):
        validate_answer(answer, [make_chunk(version="old")], "v1")


def test_one_repair_then_failure(make_chunk):
    class BadLLM:
        n = 0

        def generate(self, *args, **kwargs):
            self.n += 1
            return Answer(
                status="answered",
                statements=[Statement(text="Unsupported", evidence_ids=["fake"])],
                limitations=[],
            )

    llm = BadLLM()
    with pytest.raises(ValueError, match="generation_validation_failed"):
        answer_question(llm, "Question", [make_chunk()], [], "v1")
    assert llm.n == 2


def test_abstention_has_no_fabricated_statements():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Answer(
            status="insufficient_evidence",
            statements=[Statement(text="A fact", evidence_ids=["x"])],
            limitations=[],
        )


def test_displayed_path_revalidates_quote_and_corpus(make_chunk, make_assertion):
    c = make_chunk()
    bad = make_assertion(quote="not in source")
    p = GraphPath(nodes=["checkout", "shipping"], assertions=[bad])
    assert select_context([], [p], {"c1": c}, len)[2] == ["invalid_path_provenance"]
    bad = make_assertion(version="other")
    p = GraphPath(nodes=["checkout", "shipping"], assertions=[bad])
    assert select_context([], [p], {"c1": c}, len)[1] == []
