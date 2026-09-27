"""Revision 0001: pgvector extension and users table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from appfit.config import EMAIL_MAX_LEN, IDENT_MAX_LEN, NAME_MAX_LEN, PROVIDER_MAX_LEN
from appfit.db.migration_utils import UUID, enum_check, enum_column

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(EMAIL_MAX_LEN), nullable=False),
        sa.Column("display_name", sa.String(NAME_MAX_LEN), nullable=False),
        sa.Column("password_hash", sa.String(IDENT_MAX_LEN)),
        enum_column("role", default="viewer"),
        sa.Column("auth_provider", sa.String(PROVIDER_MAX_LEN), nullable=False, server_default="local"),
        sa.Column("external_subject", sa.String(IDENT_MAX_LEN)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        enum_check("users", "role", ["viewer", "editor", "admin"]),
    )


def downgrade() -> None:
    op.drop_table("users")
