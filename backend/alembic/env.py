"""Alembic environment — uses DATABASE_URL from application config."""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, create_engine

# Ensure backend package root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import DATABASE_URL  # noqa: E402
from database import Base  # noqa: E402
import models  # noqa: F401, E402
import domain.models_ext  # noqa: F401, E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    ul = url.lower()
    if ("supabase.co" in ul or "supabase.com" in ul) and "sslmode=" not in ul:
        return {"sslmode": "require"}
    if os.environ.get("DB_SSLMODE", "").strip():
        return {"sslmode": os.environ["DB_SSLMODE"].strip()}
    return {}


def run_migrations_online() -> None:
    connectable = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args=_connect_args(DATABASE_URL),
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
