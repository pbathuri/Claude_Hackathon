"""
Database setup with SQLAlchemy.
Local dev: SQLite. Production: PostgreSQL with connection pooling.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool, QueuePool

from config import DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")
_db_lower = DATABASE_URL.lower()

_engine_kwargs = {"echo": False}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["poolclass"] = QueuePool
    _engine_kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "5"))
    _engine_kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
    _engine_kwargs["pool_pre_ping"] = True
    # Supabase and many cloud Postgres providers require TLS
    if ("supabase.co" in _db_lower or "supabase.com" in _db_lower) and "sslmode=" not in _db_lower:
        _engine_kwargs["connect_args"] = {"sslmode": "require"}
    elif os.environ.get("DB_SSLMODE", "").strip():
        _engine_kwargs["connect_args"] = {"sslmode": os.environ["DB_SSLMODE"].strip()}

# Serverless-friendly pool when explicitly requested (e.g. some hosted Postgres)
if not _is_sqlite and os.environ.get("DB_USE_NULL_POOL", "").lower() in ("1", "true", "yes"):
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs.pop("pool_size", None)
    _engine_kwargs.pop("max_overflow", None)

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables on SQLite; on PostgreSQL use Alembic unless DB_ALLOW_CREATE_ALL=1."""
    # Import extended models so create_all creates their tables
    try:
        from domain.models_ext import (  # noqa: F401
            ConversationTurnRecord,
            ConsentEventRecord,
            ClinicalExtractionRecord,
            OutboxJob,
        )
    except ImportError:
        pass

    if not _is_sqlite and os.environ.get("DB_ALLOW_CREATE_ALL", "").lower() not in ("1", "true", "yes"):
        import logging

        logging.getLogger(__name__).info(
            "PostgreSQL detected — skipping metadata.create_all (run `alembic upgrade head`)."
        )
        return

    Base.metadata.create_all(bind=engine)
