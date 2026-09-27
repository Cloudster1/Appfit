"""Revision 0002: catalog tables (apps, capabilities, tags, maintainers)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from appfit.config import (
    CAPABILITY_DETAILS_MAX_LEN,
    CAPABILITY_TEXT_MAX_LEN,
    EMAIL_MAX_LEN,
    HASH_LEN,
    NAME_MAX_LEN,
    SHORT_DESCRIPTION_MAX_LEN,
    SHORT_TEXT_MAX_LEN,
    SLUG_MAX_LEN,
    URL_MAX_LEN,
)
from appfit.db.migration_utils import UUID, enum_check, enum_column, timestamp_column

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fk(column: str, target: str, name: str, ondelete: str = "CASCADE", nullable: bool = False) -> sa.Column:
    return sa.Column(column, UUID, sa.ForeignKey(target, ondelete=ondelete, name=name), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(SHORT_TEXT_MAX_LEN), nullable=False),
        enum_column("category", default="general"),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        enum_check("tags", "category", ["general", "tech", "domain"]),
    )
    op.create_index("uq_tags_category_name", "tags", ["category", "name"], unique=True)

    op.create_table(
        "maintainers",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(NAME_MAX_LEN), nullable=False),
        sa.Column("email", sa.String(EMAIL_MAX_LEN)),
        enum_column("kind", default="person"),
        sa.Column("org_unit", sa.String(NAME_MAX_LEN)),
        sa.Column("url", sa.String(URL_MAX_LEN)),
        sa.PrimaryKeyConstraint("id", name="pk_maintainers"),
        sa.UniqueConstraint("email", name="uq_maintainers_email"),
        enum_check("maintainers", "kind", ["person", "team"]),
    )

    op.create_table(
        "apps",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("slug", sa.String(SLUG_MAX_LEN), nullable=False),
        sa.Column("name", sa.String(NAME_MAX_LEN), nullable=False),
        sa.Column("short_description", sa.String(SHORT_DESCRIPTION_MAX_LEN), nullable=False, server_default=""),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        enum_column("lifecycle_status", default="active"),
        sa.Column("license", sa.String(SHORT_TEXT_MAX_LEN)),
        enum_column("license_type", nullable=True),
        sa.Column("vendor", sa.String(NAME_MAX_LEN)),
        sa.Column("version", sa.String(SHORT_TEXT_MAX_LEN)),
        sa.Column("homepage_url", sa.String(URL_MAX_LEN)),
        sa.Column("repo_url", sa.String(URL_MAX_LEN)),
        sa.Column("docs_url", sa.String(URL_MAX_LEN)),
        sa.Column("links", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("extra", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("search_tsv", postgresql.TSVECTOR),
        _fk("created_by", "users.id", "fk_apps_created_by_users", ondelete="SET NULL", nullable=True),
        _fk("updated_by", "users.id", "fk_apps_updated_by_users", ondelete="SET NULL", nullable=True),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id", name="pk_apps"),
        sa.UniqueConstraint("slug", name="uq_apps_slug"),
        enum_check("apps", "lifecycle_status", ["idea", "pilot", "active", "deprecated", "retired"]),
        enum_check("apps", "license_type", ["oss", "commercial", "internal", "other"], nullable=True),
    )
    op.create_index("ix_apps_search_tsv", "apps", ["search_tsv"], postgresql_using="gin")
    op.create_index("ix_apps_lifecycle_status", "apps", ["lifecycle_status"])

    op.create_table(
        "app_capabilities",
        sa.Column("id", UUID, primary_key=True),
        _fk("app_id", "apps.id", "fk_app_capabilities_app_id_apps"),
        enum_column("kind", default="capability"),
        sa.Column("text", sa.String(CAPABILITY_TEXT_MAX_LEN), nullable=False),
        sa.Column("details", sa.String(CAPABILITY_DETAILS_MAX_LEN)),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(HASH_LEN)),
        sa.PrimaryKeyConstraint("id", name="pk_app_capabilities"),
        enum_check("app_capabilities", "kind", ["capability", "requirement", "feature"]),
    )
    op.create_index("ix_app_capabilities_app_id", "app_capabilities", ["app_id"])
    op.create_index("uq_app_capabilities_app_text", "app_capabilities", ["app_id", sa.text("lower(text)")], unique=True)

    op.create_table(
        "app_tags",
        _fk("app_id", "apps.id", "fk_app_tags_app_id_apps"),
        _fk("tag_id", "tags.id", "fk_app_tags_tag_id_tags"),
        sa.PrimaryKeyConstraint("app_id", "tag_id", name="pk_app_tags"),
    )
    op.create_index("ix_app_tags_tag_id", "app_tags", ["tag_id"])

    op.create_table(
        "app_maintainers",
        _fk("app_id", "apps.id", "fk_app_maintainers_app_id_apps"),
        _fk("maintainer_id", "maintainers.id", "fk_app_maintainers_maintainer_id_maintainers"),
        enum_column("role"),
        sa.PrimaryKeyConstraint("app_id", "maintainer_id", "role", name="pk_app_maintainers"),
        enum_check("app_maintainers", "role", ["owner", "maintainer", "contact"]),
    )
    op.create_index("ix_app_maintainers_maintainer_id", "app_maintainers", ["maintainer_id"])


def downgrade() -> None:
    for table in ("app_maintainers", "app_tags", "app_capabilities", "apps", "maintainers", "tags"):
        op.drop_table(table)
