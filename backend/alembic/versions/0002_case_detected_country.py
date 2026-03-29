"""Add cases.detected_country_code for phone-parse audit trail.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "cases" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("cases")}
    if "detected_country_code" not in cols:
        op.add_column(
            "cases",
            sa.Column("detected_country_code", sa.String(length=3), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "cases" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("cases")}
    if "detected_country_code" in cols:
        op.drop_column("cases", "detected_country_code")
