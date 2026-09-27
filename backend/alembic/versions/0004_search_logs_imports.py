"""Revision 0004: search logs (with feedback) and import runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from appfit.config import IDENT_MAX_LEN, PROVIDER_MAX_LEN
from appfit.db.migration_utils import UUID, timestamp_column

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _user_fk(table: str) -> sa.Column:
    return sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL", name=f"fk_{table}_user_id_users"))


def upgrade() -> None:
    op.create_table(
        "search_logs",
        sa.Column("id", UUID, primary_key=True),
        _user_fk("search_logs"),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("requirements", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("filters", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("results", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("no_match", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("embedding_model", sa.String(IDENT_MAX_LEN)),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("feedback", postgresql.JSONB),
        timestamp_column("created_at"),
        sa.PrimaryKeyConstraint("id", name="pk_search_logs"),
    )
    op.create_index("ix_search_logs_created_at", "search_logs", ["created_at"])

    op.create_table(
        "import_runs",
        sa.Column("id", UUID, primary_key=True),
        _user_fk("import_runs"),
        sa.Column("filename", sa.String(IDENT_MAX_LEN)),
        sa.Column("format", sa.String(PROVIDER_MAX_LEN), nullable=False),
        sa.Column("mode", sa.String(PROVIDER_MAX_LEN), nullable=False),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("stats", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("errors", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        timestamp_column("created_at"),
        sa.PrimaryKeyConstraint("id", name="pk_import_runs"),
    )


def downgrade() -> None:
    op.drop_table("import_runs")
    op.drop_table("search_logs")
