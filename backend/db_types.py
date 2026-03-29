"""Cross-dialect column types: JSONB on PostgreSQL, JSON on SQLite."""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# PostgreSQL uses JSONB; SQLite and others use generic JSON
JSONCompat = JSON().with_variant(JSONB(), "postgresql")
