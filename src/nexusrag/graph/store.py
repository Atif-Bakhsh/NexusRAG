"""Only these developer-owned read templates accept question-derived parameters."""

import json

from neo4j import GraphDatabase, Query

from nexusrag.config import Settings
from nexusrag.models import Assertion, GraphPath, Plan

SCOPE = """
all(n IN nodes(p) WHERE n.corpus_version = $version) AND
all(n IN nodes(p) WHERE single(m IN nodes(p) WHERE m = n)) AND
all(r IN relationships(p) WHERE r.corpus_version = $version)
"""
# Message flow traverses CONSUMES_FROM against its stored semantic direction.
FLOW = """
all(i IN range(0, size(relationships(p))-1) WHERE
  (type(relationships(p)[i]) = 'CONSUMES_FROM' AND
   endNode(relationships(p)[i]) = nodes(p)[i]) OR
  (type(relationships(p)[i]) <> 'CONSUMES_FROM' AND
   startNode(relationships(p)[i]) = nodes(p)[i]))
"""
REQUIRED = """
all(id IN $required WHERE any(n IN nodes(p) WHERE n.entity_id = id))
AND all(i IN range(0, size($required)-2) WHERE
 head([j IN range(0,size(nodes(p))-1) WHERE nodes(p)[j].entity_id = $required[i]]) <
 head([j IN range(0,size(nodes(p))-1) WHERE nodes(p)[j].entity_id = $required[i+1]]))
"""
TAIL = """
RETURN [n IN nodes(p) | n.entity_id] AS nodes,
       [r IN relationships(p) | r.payload] AS assertions
ORDER BY length(p), [n IN nodes(p) | n.entity_id] LIMIT 21
"""
TEMPLATES = {
    "neighbors": "MATCH p=(s:Entity)-[:CALLS|USES_STORE|PUBLISHES_TO|CONSUMES_FROM]->(:Entity) "
    "WHERE s.entity_id=$start AND " + SCOPE + TAIL,
    "paths": "MATCH p=(s:Entity)-[:CALLS|USES_STORE*1..3]->(:Entity) "
    "WHERE s.entity_id=$start AND " + SCOPE + " AND " + REQUIRED + TAIL,
    "reverse": "MATCH p=(s:Entity)<-[:CALLS|USES_STORE*1..3]-(:Entity) "
    "WHERE s.entity_id=$start AND " + SCOPE + " AND " + REQUIRED + TAIL,
    "messaging": "MATCH p=(s:Entity)-[:CALLS|USES_STORE|PUBLISHES_TO|CONSUMES_FROM*1..3]-(:Entity) "
    "WHERE s.entity_id=$start AND "
    + SCOPE
    + " AND "
    + FLOW
    + " AND "
    + REQUIRED
    + " AND any(r IN relationships(p) WHERE type(r) IN ['PUBLISHES_TO','CONSUMES_FROM']) "
    + TAIL,
    "shared": "MATCH p=(s:Entity)-[:CALLS]->(:Entity)<-[:CALLS]-(t:Entity) "
    "WHERE s.entity_id=$start AND t.entity_id=$other AND " + SCOPE + TAIL,
}


class GraphStore:
    def __init__(self, settings: Settings):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
            connection_timeout=5,
            max_transaction_retry_time=0,
        )

    def close(self):
        self.driver.close()

    def ping(self):
        self.driver.verify_connectivity()

    def import_assertions(self, version: str, entities: list, assertions: list[Assertion]):
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (n:Entity) REQUIRE n.key IS UNIQUE"
            ).consume()
            session.run(
                "CREATE CONSTRAINT corpus_key IF NOT EXISTS FOR (n:Corpus) REQUIRE n.version IS UNIQUE"
            ).consume()
            with session.begin_transaction(timeout=30) as tx:
                for entity in entities:
                    tx.run(
                        "MERGE (n:Entity {key:$key}) SET n.entity_id=$id, n.corpus_version=$version, "
                        "n.name=$name, n.entity_type=$type, n.payload=$payload",
                        key=f"{version}:{entity.entity_id}",
                        id=entity.entity_id,
                        version=version,
                        name=entity.name,
                        type=entity.entity_type,
                        payload=entity.model_dump_json(),
                    ).consume()
                for assertion in assertions:
                    # Predicate is an enum validated before interpolation, never question text.
                    if assertion.predicate not in {
                        "CALLS",
                        "USES_STORE",
                        "PUBLISHES_TO",
                        "CONSUMES_FROM",
                    }:
                        raise ValueError("Invalid predicate")
                    tx.run(
                        "MATCH (s:Entity {key:$subject}), (o:Entity {key:$object}) "
                        f"MERGE (s)-[r:{assertion.predicate} {{assertion_id:$id}}]->(o) "
                        "SET r.corpus_version=$version, r.payload=$payload",
                        subject=f"{version}:{assertion.subject}",
                        object=f"{version}:{assertion.object}",
                        id=assertion.assertion_id,
                        version=version,
                        payload=assertion.model_dump_json(),
                    ).consume()
                tx.run(
                    "MERGE (c:Corpus {version:$version}) SET c.assertion_count=$count",
                    version=version,
                    count=len(assertions),
                ).consume()
                tx.commit()

    def ready(self, version: str) -> bool:
        with self.driver.session(default_access_mode="READ") as session:
            row = session.run(
                Query(
                    "MATCH (c:Corpus {version:$v}) "
                    "OPTIONAL MATCH (:Entity {corpus_version:$v})-[r]->(:Entity {corpus_version:$v}) "
                    "WHERE r.corpus_version=$v "
                    "RETURN c.assertion_count AS expected, count(r) AS actual",
                    timeout=2,
                ),
                v=version,
            ).single()
            return bool(row is not None and row["expected"] == row["actual"])

    def assertions(self, version: str) -> list[Assertion]:
        """Read stored provenance for this small corpus's readiness audit."""
        with self.driver.session(default_access_mode="READ") as session:
            rows = session.run(
                Query(
                    "MATCH (:Entity {corpus_version:$v})-[r]->(:Entity {corpus_version:$v}) "
                    "WHERE r.corpus_version=$v RETURN r.payload AS payload",
                    timeout=2,
                ),
                v=version,
            )
            return [Assertion.model_validate_json(row["payload"]) for row in rows]

    def retrieve(self, plan: Plan, version: str) -> tuple[list[GraphPath], bool]:
        if plan.template_id is None or not plan.matched_entities:
            return [], False
        template = "reverse" if plan.reverse else plan.template_id
        ids = plan.matched_entities
        with self.driver.session(default_access_mode="READ") as session:
            records = list(
                session.run(
                    Query(TEMPLATES[template], timeout=2),
                    version=version,
                    start=ids[0],
                    other=ids[-1],
                    required=ids,
                )
            )
        paths = [
            GraphPath(
                nodes=r["nodes"],
                assertions=[Assertion.model_validate(json.loads(a)) for a in r["assertions"]],
            )
            for r in records[:20]
        ]
        return paths, len(records) > 20
