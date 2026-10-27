"""expected churners of older runs

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-27 21:05:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Runs trained before summaries had `expected_churners` get it the way training computes
    # it: the sum of the run's stored probabilities.
    op.execute(
        """
        UPDATE churn_runs AS run
        SET result = jsonb_set(
            run.result,
            '{summary,expected_churners}',
            to_jsonb((
                SELECT coalesce(sum(score.probability), 0)
                FROM churn_scores AS score
                WHERE score.run_id = run.id
            ))
        )
        WHERE jsonb_typeof(run.result -> 'summary') = 'object'
            AND run.result #> '{summary,expected_churners}' IS NULL
        """
    )


def downgrade() -> None:
    pass  # older code ignores the added value
