import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import conv

from appfit.config import ENUM_MAX_LEN

UUID = postgresql.UUID(as_uuid=True)


def enum_column(name: str, *, nullable: bool = False, default: str | None = None) -> sa.Column:
    return sa.Column(name, sa.String(ENUM_MAX_LEN), nullable=nullable, server_default=default)


def enum_check(table: str, column: str, values: list[str], nullable: bool = False) -> sa.CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    cond = f"{column} IN ({allowed})"
    if nullable:
        cond = f"{column} IS NULL OR {cond}"
    return sa.CheckConstraint(cond, name=conv(f"ck_{table}_{column}"))


def timestamp_column(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
