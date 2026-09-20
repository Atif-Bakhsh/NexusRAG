import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from nexusrag.config import Settings
from nexusrag.db import ChunkRow, CorpusRow, DocumentRow, QueryRow, Repository
from nexusrag.graph.ontology import Registry
from nexusrag.graph.store import GraphStore
from nexusrag.ingestion.corpus import load_corpus
from nexusrag.models import Plan

pytestmark = pytest.mark.integration


@pytest.fixture
def databases(make_chunk, make_assertion):
    settings = Settings()
    repo, graph = Repository(settings), GraphStore(settings)
    version = "test-" + uuid.uuid4().hex
    manifest, _ = load_corpus(Path("corpus"))
    manifest.corpus_version = version
    repo.stage(manifest, settings.fingerprint())
    specs = [
        ("frontend", "CALLS", "checkout"),
        ("checkout", "CALLS", "shipping"),
        ("shipping", "CALLS", "quote"),
        ("checkout", "PUBLISHES_TO", "kafka"),
        ("accounting", "CONSUMES_FROM", "kafka"),
        ("accounting", "USES_STORE", "postgresql"),
        ("frontend", "CALLS", "shipping"),
    ]
    chunks = []
    assertions = []
    for i, (s, p, o) in enumerate(specs):
        c = make_chunk(f"{version}-{i}", f"{s} {p} {o}\n", version=version)
        chunks.append(c)
        assertions.append(make_assertion(s, p, o, c.chunk_id, c.text, version, f"{version}-a{i}"))
    vectors = []
    for i in range(len(chunks)):
        vector = [0.0] * 384
        vector[i] = 1
        vectors.append(vector)
    repo.store_chunks(chunks, vectors)
    graph.import_assertions(version, list(Registry().entities.values()), assertions)
    repo.mark_ready(version)
    try:
        yield repo, graph, version, chunks, assertions, vectors
    finally:
        with graph.driver.session() as session:
            session.run("MATCH (n:Entity {corpus_version:$v}) DETACH DELETE n", v=version).consume()
            session.run("MATCH (n:Corpus {version:$v}) DELETE n", v=version).consume()
        graph.close()
        with Session(repo.engine) as session, session.begin():
            for cls in [QueryRow, ChunkRow, DocumentRow]:
                session.execute(delete(cls).where(cls.corpus_version == version))
            session.execute(delete(CorpusRow).where(CorpusRow.version == version))
        repo.engine.dispose()


def test_exact_cosine_filters_and_idempotence(databases):
    repo, _, version, chunks, _, vectors = databases
    repo.store_chunks(chunks, vectors)
    ranked = repo.search(vectors[0], version)
    assert ranked[0][0].chunk_id == chunks[0].chunk_id
    assert ranked[0][1] == pytest.approx(1)
    assert all(score == pytest.approx(0) for _, score in ranked[1:])
    assert repo.search(vectors[0], version, document_filter=["cart"]) == []
    assert repo.search(vectors[0], "absent") == []
    with Session(repo.engine) as s:
        assert s.scalar(
            select(func.count()).select_from(ChunkRow).where(ChunkRow.corpus_version == version)
        ) == len(chunks)
        row = s.get(CorpusRow, version)
        row.ready = False
        s.commit()
    assert repo.search(vectors[0], version) == []


def test_graph_templates_directions_scoping_and_idempotence(databases):
    _, g, v, _, assertions, _ = databases
    g.import_assertions(v, list(Registry().entities.values()), assertions)
    p, _ = g.retrieve(
        Plan(template_id="paths", matched_entities=["frontend", "checkout", "shipping", "quote"]), v
    )
    assert len(p) == 1 and p[0].nodes == ["frontend", "checkout", "shipping", "quote"]
    assert len(p[0].assertions) == 3
    reverse, _ = g.retrieve(Plan(template_id="paths", matched_entities=["quote"], reverse=True), v)
    assert any(x.nodes == ["quote", "shipping", "checkout", "frontend"] for x in reverse)
    message, _ = g.retrieve(
        Plan(template_id="messaging", matched_entities=["checkout", "accounting"]), v
    )
    assert any(x.nodes == ["checkout", "kafka", "accounting"] for x in message)
    assert any(x.nodes == ["checkout", "kafka", "accounting", "postgresql"] for x in message)
    shared, _ = g.retrieve(Plan(template_id="shared", matched_entities=["frontend", "checkout"]), v)
    assert [x.nodes for x in shared] == [["frontend", "shipping", "checkout"]]
    direct, _ = g.retrieve(Plan(template_id="neighbors", matched_entities=["accounting"]), v)
    assert {x.assertions[0].predicate for x in direct} == {"CONSUMES_FROM", "USES_STORE"}
    assert g.retrieve(Plan(template_id="neighbors", matched_entities=["checkout"]), "other") == (
        [],
        False,
    )
    for path in p + reverse + message + shared + direct:
        assert len(path.nodes) == len(set(path.nodes)) and len(path.assertions) <= 3
        assert all(a.evidence for a in path.assertions)


def test_graph_timeout_is_explicit(databases):
    from neo4j import Query
    from neo4j.exceptions import Neo4jError

    _, g, *_ = databases
    with g.driver.session() as session:
        with pytest.raises(Neo4jError):
            list(session.run(Query("UNWIND range(1,100000000) AS n RETURN sum(n)", timeout=0.001)))


def test_graph_twenty_path_cap_reports_truncation(databases, make_assertion, make_chunk):
    from nexusrag.models import Entity

    repo, g, v, chunks, assertions, _ = databases
    entities = []
    extra = []
    for i in range(25):
        id_ = f"test-target-{i}"
        entities.append(
            Entity(entity_id=id_, name=id_, entity_type="Service", aliases=[], mentions=[])
        )
        extra.append(
            make_assertion(
                "checkout", "CALLS", id_, chunks[0].chunk_id, chunks[0].text, v, f"{v}-extra-{i}"
            )
        )
    g.import_assertions(v, entities, extra)
    paths, truncated = g.retrieve(Plan(template_id="neighbors", matched_entities=["checkout"]), v)
    assert len(paths) == 20 and truncated is True
