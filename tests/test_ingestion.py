from pathlib import Path

import pytest

from nexusrag.config import Settings
from nexusrag.evaluation.runner import load_questions
from nexusrag.ingestion.chunking import chunk_document
from nexusrag.ingestion.corpus import digest, load_corpus
from nexusrag.models import Document


def document(raw):
    return Document(
        document_id="test",
        path="docs/test.md",
        repository_path="test.md",
        source_url="https://example.org/test.md",
        sha256=digest(raw),
    )


def test_manifest_and_all_labels_are_valid():
    manifest, documents = load_corpus(Path("corpus"))
    questions = load_questions(Path("evaluation/questions.jsonl"), Settings())
    assert len(manifest.documents) == len(documents) == 12
    assert len(questions) == 40
    assert sum(q.split == "dev" for q in questions) == 16
    assert all(q.review_status == "source_checked_by_agent" for q in questions)


def test_chunks_preserve_lines_fences_limits_and_identity():
    raw = (
        "---\ntitle: Test\n---\n# Top\n\nIntro.\n\n```mermaid\n"
        + "".join(f"s{i} --> s{i + 1}\n" for i in range(50))
        + "```\n\n## Next\n\nEnd.\n"
    )

    def count(s):
        return len(s.split())

    first = chunk_document(document(raw), raw, "v1", count, target=30, maximum=40, overlap=6)
    second = chunk_document(document(raw), raw, "v1", count, target=30, maximum=40, overlap=6)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert len(first) > 3
    for c in first:
        assert c.text == "".join(raw.splitlines(keepends=True)[c.line_start - 1 : c.line_end])
        assert count(c.embedding_text) <= 40
        assert c.page_number is None
    assert "s49 --> s50" in "".join(c.text for c in first)
    assert first[-1].section == "Top / Next"
    other = chunk_document(document(raw), raw, "v2", count, target=30, maximum=40)
    assert set(c.chunk_id for c in first).isdisjoint(c.chunk_id for c in other)


def test_oversized_line_fails_instead_of_silently_truncating():
    raw = "# Heading\n" + "word " * 100
    with pytest.raises(ValueError, match="Single source line"):
        chunk_document(document(raw), raw, "v", lambda s: len(s.split()), maximum=20)


def test_tampered_manifest_is_rejected(tmp_path):
    import shutil

    shutil.copytree("corpus", tmp_path / "corpus")
    (tmp_path / "corpus/docs/cart.md").write_text("changed")
    with pytest.raises(ValueError, match="Checksum"):
        load_corpus(tmp_path / "corpus")


@pytest.mark.model
def test_real_embedding_tokenizer_all_chunks():
    from nexusrag.ingestion.pipeline import prepare
    from nexusrag.retrieval.embeddings import Embedder

    settings = Settings()
    e = Embedder(settings)
    _, chunks = prepare(settings, e)
    assert all(e.count(c.embedding_text) <= 320 for c in chunks)
    assert len(e.query("What does Checkout call?")) == 384


@pytest.mark.model
def test_all_gold_source_spans_map_to_real_chunks():
    from nexusrag.evaluation.metrics import map_gold
    from nexusrag.ingestion.pipeline import prepare
    from nexusrag.retrieval.embeddings import Embedder

    settings = Settings()
    _, chunks = prepare(settings, Embedder(settings))
    for question in load_questions(Path("evaluation/questions.jsonl"), settings):
        _, alternatives = map_gold(question, chunks)
        assert all(cover for spans in alternatives for cover in spans), question.id
