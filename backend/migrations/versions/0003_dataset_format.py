"""dataset format

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14 21:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("format", sa.String(length=20), nullable=True))
    op.alter_column("datasets", "schema_version", existing_type=sa.Integer(), nullable=True)
    op.execute(
        "UPDATE datasets SET format = CASE schema_version WHEN 1 THEN 'nested' "
        "WHEN 0 THEN NULL ELSE 'tabular' END, "
        "schema_version = CASE WHEN schema_version > 1 THEN schema_version END"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE datasets SET schema_version = CASE format WHEN 'nested' THEN 1 "
        "WHEN 'tabular' THEN schema_version ELSE 0 END"
    )
    op.alter_column("datasets", "schema_version", existing_type=sa.Integer(), nullable=False)
    op.drop_column("datasets", "format")
