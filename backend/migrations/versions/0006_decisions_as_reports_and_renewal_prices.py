"""decisions as reports and renewal prices

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27 16:42:49.400523
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("churn_scores", sa.Column("period_price", sa.Double(), nullable=True))
    op.add_column(
        "reports",
        sa.Column("kind", sa.String(length=20), server_default="analytics", nullable=False),
    )
    op.add_column(
        "reports", sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("reports", "params")
    op.drop_column("reports", "kind")
    op.drop_column("churn_scores", "period_price")
