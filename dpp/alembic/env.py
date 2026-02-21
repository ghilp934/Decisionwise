"""Alembic environment configuration.

Spec Lock:
  - URL resolution: DATABASE_URL_MIGRATIONS > DATABASE_URL > alembic.ini
  - Online migration uses build_engine() — inherits full SSL SSOT policy
    (verify-full in PROD, sslrootcert from DPP_DB_SSLROOTCERT, NullPool default).
  - No separate ssl injection needed here; ssl_policy handles it via build_engine().
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool

# Add apps/api to path so dpp_api imports resolve.
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from dpp_api.db.engine import build_engine  # noqa: E402
from dpp_api.db.models import Base  # noqa: E402

# Alembic Config object — provides access to values in the .ini file.
config = context.config

# Set up logging from the alembic.ini config file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support.
target_metadata = Base.metadata

# Spec Lock: Inject DATABASE_URL from environment.
# Priority: DATABASE_URL_MIGRATIONS (migration-specific) > DATABASE_URL (runtime) > alembic.ini
database_url = (
    os.getenv("DATABASE_URL_MIGRATIONS")
    or os.getenv("DATABASE_URL")
    or config.get_main_option("sqlalchemy.url")
)

if not database_url:
    raise ValueError(
        "Database URL not configured. "
        "Set DATABASE_URL_MIGRATIONS or DATABASE_URL environment variable, "
        "or configure sqlalchemy.url in alembic.ini."
    )

# Expose the resolved URL to alembic.ini (used by offline mode and Alembic internals).
# SSL policy is applied inside build_engine() for the online path; offline mode
# generates SQL without connecting, so SSL is not enforced there.
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL generation, no DB connection).

    Configures the context with a URL and emits SQL to stdout/file.
    SSL is not enforced in offline mode (no actual connection is made).
    """
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
    """Run migrations in 'online' mode (direct DB connection).

    Uses build_engine() as the SSOT engine builder so that:
      - SSL policy (verify-full in PROD + sslrootcert) is automatically applied.
      - NullPool is used by default (DPP Spec Lock for Supabase pooler).
      - Production guardrails (port 6543, pooler host, ACK vars) are enforced.

    Raises:
        RuntimeError: Production guardrail failure (SSL, port, pooler, ACK checks).
        ValueError: DATABASE_URL not resolvable.
    """
    connectable = build_engine(database_url)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
