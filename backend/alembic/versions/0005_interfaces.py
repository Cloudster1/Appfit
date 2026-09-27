"""Revision 0005: external systems and interfaces (data flows between apps and systems)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import conv

from appfit.config import (
    EMBEDDING_DIM,
    HASH_LEN,
    HNSW_EF_CONSTRUCTION,
    HNSW_M,
    IDENT_MAX_LEN,
    NAME_MAX_LEN,
    SHORT_TEXT_MAX_LEN,
    URL_MAX_LEN,
)
from appfit.db.migration_utils import UUID, enum_check, enum_column, timestamp_column

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HNSW_OPTS = {"postgresql_using": "hnsw", "postgresql_with": {"m": HNSW_M, "ef_construction": HNSW_EF_CONSTRUCTION}}
TYPES = ["rest_api", "soap", "file_transfer", "database", "messaging", "sso", "ui_embedding", "other"]
ENDPOINTS = ("from_app_id", "from_system_id", "to_app_id", "to_system_id")


def _fk(column: str, target: str, ondelete: str) -> sa.Column:
    table = target.split(".")[0]
    return sa.Column(column, UUID, sa.ForeignKey(target, ondelete=ondelete, name=f"fk_interfaces_{column}_{table}"))


def _check(name: str, cond: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(cond, name=conv(f"ck_interfaces_{name}"))


def upgrade() -> None:
    op.create_table(
        "external_systems",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(NAME_MAX_LEN), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("vendor", sa.String(NAME_MAX_LEN)),
        sa.Column("url", sa.String(URL_MAX_LEN)),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id", name="pk_external_systems"),
    )
    op.create_index("uq_external_systems_name", "external_systems", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "interfaces",
        sa.Column("id", UUID, primary_key=True),
        _fk("from_app_id", "apps.id", "CASCADE"),
        _fk("from_system_id", "external_systems.id", "RESTRICT"),
        _fk("to_app_id", "apps.id", "CASCADE"),
        _fk("to_system_id", "external_systems.id", "RESTRICT"),
        sa.Column("name", sa.String(NAME_MAX_LEN), nullable=False),
        enum_column("interface_type", default="other"),
        sa.Column(
            "data_objects",
            postgresql.ARRAY(sa.String(SHORT_TEXT_MAX_LEN)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        enum_column("frequency", nullable=True),
        enum_column("status", default="active"),
        sa.Column("bidirectional", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(HASH_LEN)),
        # One vector per catalog-app side, from that app's point of view (null on a system side).
        sa.Column("from_embedding", Vector(EMBEDDING_DIM)),
        sa.Column("to_embedding", Vector(EMBEDDING_DIM)),
        sa.Column("embedding_model", sa.String(IDENT_MAX_LEN)),
        sa.Column("embedded_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_interfaces_created_by_users")
        ),
        sa.Column(
            "updated_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_interfaces_updated_by_users")
        ),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id", name="pk_interfaces"),
        enum_check("interfaces", "interface_type", TYPES),
        enum_check("interfaces", "frequency", ["realtime", "batch", "on_demand"], nullable=True),
        enum_check("interfaces", "status", ["planned", "active", "deprecated"]),
        # Each side is exactly one app or one external system.
        _check("one_source", "(from_app_id IS NULL) <> (from_system_id IS NULL)"),
        _check("one_target", "(to_app_id IS NULL) <> (to_system_id IS NULL)"),
        _check("has_app", "from_app_id IS NOT NULL OR to_app_id IS NOT NULL"),
        _check("not_self", "from_app_id IS NULL OR to_app_id IS NULL OR from_app_id <> to_app_id"),
    )
    for column in ENDPOINTS:
        op.create_index(f"ix_interfaces_{column}", "interfaces", [column])
    op.create_index(
        "uq_interfaces_endpoints_name",
        "interfaces",
        [
            sa.text("coalesce(from_app_id, from_system_id)"),
            sa.text("coalesce(to_app_id, to_system_id)"),
            sa.text("lower(name)"),
        ],
        unique=True,
    )
    for column in ("from_embedding", "to_embedding"):
        op.create_index(
            f"ix_interfaces_{column}_hnsw",
            "interfaces",
            [column],
            postgresql_ops={column: "vector_cosine_ops"},
            **HNSW_OPTS,
        )


def downgrade() -> None:
    op.drop_table("interfaces")
    op.drop_table("external_systems")
