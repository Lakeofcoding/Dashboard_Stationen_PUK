"""
Alembic Environment Configuration.

Nutzt die gleiche DB-URL und Base wie die App.
Unterstützt SQLite (dev) und PostgreSQL (prod).
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# App-eigene Konfiguration importieren
from app.db import DB_URL, Base

# Alle Modelle importieren, damit Base.metadata vollständig ist
import app.models  # noqa: F401

# Alembic Config object
config = context.config

# Logging aus alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# sqlalchemy.url dynamisch aus der App setzen
config.set_main_option("sqlalchemy.url", DB_URL)

# MetaData für autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL-Skript generieren)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (direkt auf DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
