"""
Alembic migration environment.

Supports both:
  - Online mode  (direct DB connection) — used by `alembic upgrade`
  - Offline mode (SQL script output)    — used by `alembic upgrade --sql`

The database URL is injected from app settings so it stays in sync
with the application configuration.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# ── Make the app importable ───────────────────────────────────────────────────
# Ensure the project root is on sys.path so we can import app modules.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402

# Import ALL models so Alembic sees them for autogenerate
import app.models.document  # noqa: F401, E402
import app.models.user  # noqa: F401, E402

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

# Configure Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the SYNC database URL (psycopg2) from app settings
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)

# Metadata for autogenerate support
target_metadata = Base.metadata


# ── Helpers ───────────────────────────────────────────────────────────────────

def include_object(object, name, type_, reflected, compare_to):
    """Filter out objects we don't want Alembic to manage."""
    # Skip pgvector internal tables
    if type_ == "table" and name.startswith("pg_"):
        return False
    return True


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — emits SQL to stdout without
    connecting to the DB. Useful for review or CI pipelines.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects directly to the DB.
    Enables pgvector extension before running any migration.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Ensure pgvector extension exists before migrations run
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
