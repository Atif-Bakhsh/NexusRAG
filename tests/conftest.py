import os

import pytest

from nexusrag.ingestion.corpus import digest
from nexusrag.models import Assertion, Chunk, Mention


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "integration" in item.keywords and os.getenv("RUN_INTEGRATION") != "1":
            item.add_marker(
                pytest.mark.skip(reason="Set RUN_INTEGRATION=1 with local databases running")
            )
        if "model" in item.keywords and os.getenv("RUN_MODEL") != "1":
            item.add_marker(pytest.mark.skip(reason="Set RUN_MODEL=1 after downloading BGE"))


@pytest.fixture
def make_chunk():
    def make(id_="c1", text="checkout --> shipping\n", version="v1", doc="architecture", start=1):
        return Chunk(
            chunk_id=id_,
            corpus_version=version,
            document_id=doc,
            title=doc.title(),
            source_url="https://example.org/source.md",
            section="Architecture",
            line_start=start,
            line_end=start + len(text.splitlines()) - 1,
            text=text,
            content_hash=digest(text),
        )

    return make


@pytest.fixture
def make_assertion():
    def make(
        subject="checkout",
        predicate="CALLS",
        object_="shipping",
        chunk="c1",
        quote="checkout --> shipping\n",
        version="v1",
        id_="a1",
    ):
        return Assertion(
            assertion_id=id_,
            subject=subject,
            predicate=predicate,
            object=object_,
            evidence=[Mention(chunk_id=chunk, quote=quote)],
            corpus_version=version,
            extraction_model="test",
            prompt_version="test",
        )

    return make
