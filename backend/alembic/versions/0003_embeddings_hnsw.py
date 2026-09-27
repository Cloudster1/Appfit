"""Revision 0003: embedding columns and HNSW cosine indexes.

Changing EMBEDDING_DIM later needs a new migration that alters both vector columns and rebuilds the indexes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from appfit.config import EMBEDDING_DIM, HASH_LEN, HNSW_EF_CONSTRUCTION, HNSW_M, IDENT_MAX_LEN

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HNSW_OPTS = {"postgresql_using": "hnsw", "postgresql_with": {"m": HNSW_M, "ef_construction": HNSW_EF_CONSTRUCTION}}


def upgrade() -> None:
    op.add_column("apps", sa.Column("summary_embedding", Vector(EMBEDDING_DIM)))
    op.add_column("apps", sa.Column("summary_hash", sa.String(HASH_LEN)))
    op.add_column("apps", sa.Column("embedding_model", sa.String(IDENT_MAX_LEN)))
    op.add_column("apps", sa.Column("embedded_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_apps_summary_embedding_hnsw",
        "apps",
        ["summary_embedding"],
        postgresql_ops={"summary_embedding": "vector_cosine_ops"},
        **HNSW_OPTS,
    )

    op.add_column("app_capabilities", sa.Column("embedding", Vector(EMBEDDING_DIM)))
    op.add_column("app_capabilities", sa.Column("embedding_model", sa.String(IDENT_MAX_LEN)))
    op.add_column("app_capabilities", sa.Column("embedded_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_app_capabilities_embedding_hnsw",
        "app_capabilities",
        ["embedding"],
        postgresql_ops={"embedding": "vector_cosine_ops"},
        **HNSW_OPTS,
    )


def downgrade() -> None:
    op.drop_index("ix_app_capabilities_embedding_hnsw", table_name="app_capabilities")
    for col in ("embedded_at", "embedding_model", "embedding"):
        op.drop_column("app_capabilities", col)
    op.drop_index("ix_apps_summary_embedding_hnsw", table_name="apps")
    for col in ("embedded_at", "embedding_model", "summary_hash", "summary_embedding"):
        op.drop_column("apps", col)
