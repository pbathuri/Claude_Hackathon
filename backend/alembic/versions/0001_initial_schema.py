"""Initial schema — aligns ORM metadata with database (PostgreSQL / SQLite).

Revision ID: 0001
Revises:
Create Date: 2025-03-28

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

from database import Base

import models  # noqa: F401
import domain.models_ext  # noqa: F401

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Idempotent: skip if core tables already exist (e.g. legacy SQLite from create_all)
    if inspect(bind).has_table("patients"):
        return
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
