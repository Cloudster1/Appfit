import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Table, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appfit.config import (
    CAPABILITY_DETAILS_MAX_LEN,
    CAPABILITY_TEXT_MAX_LEN,
    EMAIL_MAX_LEN,
    EMBEDDING_DIM,
    HASH_LEN,
    IDENT_MAX_LEN,
    NAME_MAX_LEN,
    SHORT_DESCRIPTION_MAX_LEN,
    SHORT_TEXT_MAX_LEN,
    SLUG_MAX_LEN,
    URL_MAX_LEN,
)
from appfit.db.base import Base
from appfit.models.enums import (
    CapabilityKind,
    InterfaceFrequency,
    InterfaceStatus,
    InterfaceType,
    LicenseType,
    LifecycleStatus,
    MaintainerKind,
    MaintainerRole,
    TagCategory,
)
from appfit.models.types import created_ts, str_enum, updated_ts, uuid_pk

app_tags = Table(
    "app_tags",
    Base.metadata,
    Column("app_id", ForeignKey("apps.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (Index("uq_tags_category_name", "category", "name", unique=True),)

    id: Mapped[uuid_pk]
    name: Mapped[str] = mapped_column(String(SHORT_TEXT_MAX_LEN))
    category: Mapped[TagCategory] = mapped_column(str_enum(TagCategory), default=TagCategory.general)


class Maintainer(Base):
    __tablename__ = "maintainers"

    id: Mapped[uuid_pk]
    name: Mapped[str] = mapped_column(String(NAME_MAX_LEN))
    email: Mapped[str | None] = mapped_column(String(EMAIL_MAX_LEN), unique=True)
    kind: Mapped[MaintainerKind] = mapped_column(str_enum(MaintainerKind), default=MaintainerKind.person)
    org_unit: Mapped[str | None] = mapped_column(String(NAME_MAX_LEN))
    url: Mapped[str | None] = mapped_column(String(URL_MAX_LEN))


class AppMaintainer(Base):
    __tablename__ = "app_maintainers"

    app_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), primary_key=True)
    maintainer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("maintainers.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[MaintainerRole] = mapped_column(str_enum(MaintainerRole), primary_key=True)

    maintainer: Mapped[Maintainer] = relationship(lazy="joined")


class App(Base):
    __tablename__ = "apps"

    id: Mapped[uuid_pk]
    slug: Mapped[str] = mapped_column(String(SLUG_MAX_LEN), unique=True)
    name: Mapped[str] = mapped_column(String(NAME_MAX_LEN))
    short_description: Mapped[str] = mapped_column(String(SHORT_DESCRIPTION_MAX_LEN), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(str_enum(LifecycleStatus), default=LifecycleStatus.active)
    license: Mapped[str | None] = mapped_column(String(SHORT_TEXT_MAX_LEN))
    license_type: Mapped[LicenseType | None] = mapped_column(str_enum(LicenseType))
    vendor: Mapped[str | None] = mapped_column(String(NAME_MAX_LEN))
    version: Mapped[str | None] = mapped_column(String(SHORT_TEXT_MAX_LEN))
    homepage_url: Mapped[str | None] = mapped_column(String(URL_MAX_LEN))
    repo_url: Mapped[str | None] = mapped_column(String(URL_MAX_LEN))
    docs_url: Mapped[str | None] = mapped_column(String(URL_MAX_LEN))
    links: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    search_tsv: Mapped[Any | None] = mapped_column(TSVECTOR, deferred=True)
    summary_embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM), deferred=True)
    summary_hash: Mapped[str | None] = mapped_column(String(HASH_LEN))
    embedding_model: Mapped[str | None] = mapped_column(String(IDENT_MAX_LEN))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]

    capabilities: Mapped[list["AppCapability"]] = relationship(
        back_populates="app",
        cascade="all, delete-orphan",
        order_by="AppCapability.position",
        lazy="selectin",
    )
    tags: Mapped[list[Tag]] = relationship(secondary=app_tags, lazy="selectin", order_by=Tag.name)
    maintainer_links: Mapped[list[AppMaintainer]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class AppCapability(Base):
    __tablename__ = "app_capabilities"

    id: Mapped[uuid_pk]
    app_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), index=True)
    kind: Mapped[CapabilityKind] = mapped_column(str_enum(CapabilityKind), default=CapabilityKind.capability)
    text: Mapped[str] = mapped_column(String(CAPABILITY_TEXT_MAX_LEN))
    details: Mapped[str | None] = mapped_column(String(CAPABILITY_DETAILS_MAX_LEN))
    position: Mapped[int] = mapped_column(default=0)

    content_hash: Mapped[str | None] = mapped_column(String(HASH_LEN))
    embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM), deferred=True)
    embedding_model: Mapped[str | None] = mapped_column(String(IDENT_MAX_LEN))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    app: Mapped[App] = relationship(back_populates="capabilities")


Index(
    "uq_app_capabilities_app_text",
    AppCapability.app_id,
    func.lower(AppCapability.text),
    unique=True,
)


class ExternalSystem(Base):
    """A system outside the catalog (e.g. SAP, a bank) that catalog apps exchange data with."""

    __tablename__ = "external_systems"

    id: Mapped[uuid_pk]
    name: Mapped[str] = mapped_column(String(NAME_MAX_LEN))
    description: Mapped[str] = mapped_column(Text, default="")
    vendor: Mapped[str | None] = mapped_column(String(NAME_MAX_LEN))
    url: Mapped[str | None] = mapped_column(String(URL_MAX_LEN))
    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]


Index("uq_external_systems_name", func.lower(ExternalSystem.name), unique=True)


class Interface(Base):
    """Data flow from one endpoint to another; each endpoint is a catalog app or an external system."""

    __tablename__ = "interfaces"

    id: Mapped[uuid_pk]
    from_app_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), index=True)
    from_system_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("external_systems.id", ondelete="RESTRICT"), index=True
    )
    to_app_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), index=True)
    to_system_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("external_systems.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(NAME_MAX_LEN))
    interface_type: Mapped[InterfaceType] = mapped_column(str_enum(InterfaceType), default=InterfaceType.other)
    data_objects: Mapped[list[str]] = mapped_column(ARRAY(String(SHORT_TEXT_MAX_LEN)), default=list)
    frequency: Mapped[InterfaceFrequency | None] = mapped_column(str_enum(InterfaceFrequency))
    status: Mapped[InterfaceStatus] = mapped_column(str_enum(InterfaceStatus), default=InterfaceStatus.active)
    bidirectional: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")

    content_hash: Mapped[str | None] = mapped_column(String(HASH_LEN))
    # Each catalog-app side gets its own vector, embedded from that app's point of view.
    from_embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM), deferred=True)
    to_embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM), deferred=True)
    embedding_model: Mapped[str | None] = mapped_column(String(IDENT_MAX_LEN))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]

    from_app: Mapped[App | None] = relationship(foreign_keys=[from_app_id], lazy="joined")
    from_system: Mapped[ExternalSystem | None] = relationship(foreign_keys=[from_system_id], lazy="joined")
    to_app: Mapped[App | None] = relationship(foreign_keys=[to_app_id], lazy="joined")
    to_system: Mapped[ExternalSystem | None] = relationship(foreign_keys=[to_system_id], lazy="joined")
