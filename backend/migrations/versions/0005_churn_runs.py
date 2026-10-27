"""churn runs

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27 14:46:11.888128
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "churn_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("chosen_model", sa.String(length=40), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_churn_runs_dataset_id_datasets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_churn_runs_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["analysts.id"],
            name=op.f("fk_churn_runs_owner_id_analysts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_churn_runs")),
        sa.UniqueConstraint("job_id", name=op.f("uq_churn_runs_job_id")),
    )
    op.create_index(op.f("ix_churn_runs_dataset_id"), "churn_runs", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_churn_runs_owner_id"), "churn_runs", ["owner_id"], unique=False)
    op.create_index(
        "uq_churn_runs_dataset_id_active",
        "churn_runs",
        ["dataset_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "churn_scores",
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("probability", sa.Double(), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["churn_runs.id"],
            name=op.f("fk_churn_scores_run_id_churn_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "user_id", name=op.f("pk_churn_scores")),
    )
    op.create_index("ix_churn_scores_run_id_rank", "churn_scores", ["run_id", "rank"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_churn_scores_run_id_rank", table_name="churn_scores")
    op.drop_table("churn_scores")
    op.drop_index(
        "uq_churn_runs_dataset_id_active",
        table_name="churn_runs",
        postgresql_where=sa.text("active"),
    )
    op.drop_index(op.f("ix_churn_runs_owner_id"), table_name="churn_runs")
    op.drop_index(op.f("ix_churn_runs_dataset_id"), table_name="churn_runs")
    op.drop_table("churn_runs")
