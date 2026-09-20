import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from nexusrag.config import Settings
from nexusrag.models import Chunk, Manifest


class Base(DeclarativeBase):
    pass


class CorpusRow(Base):
    __tablename__ = "corpora"
    version: Mapped[str] = mapped_column(String, primary_key=True)
    ready: Mapped[bool] = mapped_column(Boolean, default=False)
    manifest: Mapped[dict] = mapped_column(JSON)
    configuration: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class DocumentRow(Base):
    __tablename__ = "documents"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    corpus_version: Mapped[str] = mapped_column(ForeignKey("corpora.version"), index=True)
    document_id: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)


class ChunkRow(Base):
    __tablename__ = "chunks"
    chunk_id: Mapped[str] = mapped_column(String, primary_key=True)
    corpus_version: Mapped[str] = mapped_column(ForeignKey("corpora.version"), index=True)
    document_id: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))


class QueryRow(Base):
    __tablename__ = "query_runs"
    query_id: Mapped[str] = mapped_column(String, primary_key=True)
    corpus_version: Mapped[str] = mapped_column(ForeignKey("corpora.version"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    payload: Mapped[dict] = mapped_column(JSON)


class Repository:
    def __init__(self, settings: Settings):
        self.engine = create_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )

    def ping(self):
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def active(self) -> CorpusRow:
        with Session(self.engine) as session:
            row = session.scalar(
                select(CorpusRow)
                .where(CorpusRow.ready.is_(True))
                .order_by(CorpusRow.created_at.desc(), CorpusRow.version)
                .limit(1)
            )
            if row is None:
                raise LookupError("No ready corpus; run ingestion")
            return row

    def is_ready(self, version: str) -> bool:
        with Session(self.engine) as session:
            row = session.get(CorpusRow, version)
            return bool(row and row.ready)

    def stage(self, manifest: Manifest, configuration: dict):
        with Session(self.engine) as session, session.begin():
            session.execute(
                insert(CorpusRow)
                .values(
                    version=manifest.corpus_version,
                    ready=False,
                    manifest=manifest.model_dump(),
                    configuration=configuration,
                )
                .on_conflict_do_nothing(index_elements=[CorpusRow.version])
            )
            for doc in manifest.documents:
                session.execute(
                    insert(DocumentRow)
                    .values(
                        key=f"{manifest.corpus_version}:{doc.document_id}",
                        corpus_version=manifest.corpus_version,
                        document_id=doc.document_id,
                        payload=doc.model_dump(),
                    )
                    .on_conflict_do_nothing(index_elements=[DocumentRow.key])
                )

    def store_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]):
        if len(chunks) != len(embeddings):
            raise ValueError("Embedding count mismatch")
        with Session(self.engine) as session, session.begin():
            for chunk, vector in zip(chunks, embeddings, strict=True):
                session.execute(
                    insert(ChunkRow)
                    .values(
                        chunk_id=chunk.chunk_id,
                        corpus_version=chunk.corpus_version,
                        document_id=chunk.document_id,
                        payload=chunk.model_dump(),
                        embedding=vector,
                    )
                    .on_conflict_do_nothing(index_elements=[ChunkRow.chunk_id])
                )

    def mark_ready(self, version: str):
        with Session(self.engine) as session, session.begin():
            row = session.get(CorpusRow, version)
            if row is None:
                raise LookupError(version)
            row.ready = True

    def chunks(self, version: str, ids: list[str] | None = None) -> list[Chunk]:
        statement = select(ChunkRow).where(ChunkRow.corpus_version == version)
        if ids is not None:
            statement = statement.where(ChunkRow.chunk_id.in_(ids))
        with Session(self.engine) as session:
            return [Chunk.model_validate(r.payload) for r in session.scalars(statement)]

    def search(
        self,
        vector: list[float],
        version: str,
        k: int = 20,
        document_filter: list[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        distance = ChunkRow.embedding.cosine_distance(vector)
        statement = (
            select(ChunkRow, distance.label("distance"))
            .join(CorpusRow)
            .where(ChunkRow.corpus_version == version, CorpusRow.ready.is_(True))
        )
        if document_filter is not None:
            statement = statement.where(ChunkRow.document_id.in_(document_filter))
        statement = statement.order_by(distance, ChunkRow.chunk_id).limit(min(k, 20))
        with Session(self.engine) as session:
            return [
                (Chunk.model_validate(row.payload), 1.0 - float(d))
                for row, d in session.execute(statement)
            ]

    def save_query(self, payload: dict) -> str:
        query_id = payload.get("query_id") or str(uuid.uuid4())
        payload["query_id"] = query_id
        with Session(self.engine) as session, session.begin():
            session.add(
                QueryRow(
                    query_id=query_id, corpus_version=payload["corpus_version"], payload=payload
                )
            )
        return query_id

    def get_query(self, query_id: str) -> dict:
        with Session(self.engine) as session:
            row = session.get(QueryRow, query_id)
            if row is None:
                raise LookupError(query_id)
            return row.payload
