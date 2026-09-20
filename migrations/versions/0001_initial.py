"""Initial immutable corpus, exact vectors, and query records."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "corpora",
        sa.Column("version", sa.String(), primary_key=True),
        sa.Column("ready", sa.Boolean(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "documents",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("corpus_version", sa.String(), sa.ForeignKey("corpora.version"), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.String(), primary_key=True),
        sa.Column("corpus_version", sa.String(), sa.ForeignKey("corpora.version"), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
    )
    op.create_index("ix_documents_corpus_version", "documents", ["corpus_version"])
    op.create_index("ix_chunks_corpus_version", "chunks", ["corpus_version"])
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_table(
        "query_runs",
        sa.Column("query_id", sa.String(), primary_key=True),
        sa.Column("corpus_version", sa.String(), sa.ForeignKey("corpora.version"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("query_runs")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("corpora")
