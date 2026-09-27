from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, engine_from_config, pool, text

import appfit.models  # noqa: F401  (registers all tables on Base.metadata)
from appfit.config import MIGRATION_LOCK_KEY, get_settings
from appfit.db.base import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

# An explicitly passed URL (tests, CLI) wins over the environment.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _migrate(conn: Connection) -> None:
    context.configure(connection=conn, target_metadata=target_metadata)
    with context.begin_transaction():
        if conn.dialect.name == "postgresql":
            # Held until commit, so a second replica waits and then finds the schema at head.
            conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _migrate(connection)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as conn:
        _migrate(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
