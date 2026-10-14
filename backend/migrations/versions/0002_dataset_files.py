"""dataset files

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14 17:40:07.669119
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_files",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_dataset_files_dataset_id_datasets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", name=op.f("pk_dataset_files")),
    )
    # The content is already gzip-compressed: store it out of line without TOAST compression.
    op.execute("ALTER TABLE dataset_files ALTER COLUMN content SET STORAGE EXTERNAL")


def downgrade() -> None:
    op.drop_table("dataset_files")
