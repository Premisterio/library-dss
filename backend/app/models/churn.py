import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAt
from app.models.job import Job


class ChurnRun(CreatedAt, Base):
    """A churn model trained on a dataset by a job; its status is the job's."""

    __tablename__ = "churn_runs"
    __table_args__ = (
        Index(
            "uq_churn_runs_dataset_id_active",
            "dataset_id",
            unique=True,
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("analysts.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True
    )
    active: Mapped[bool] = mapped_column(default=False)  # the run decisions use, one per dataset
    # Set when the job succeeds.
    chosen_model: Mapped[str | None] = mapped_column(String(40))
    # summary, backtest, importance, coefficients and typical feature values
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    job: Mapped[Job] = relationship(lazy="joined")


class ChurnScore(Base):
    """The churn probability of one member at risk at the dataset's as_of, with reasons."""

    __tablename__ = "churn_scores"
    __table_args__ = (Index("ix_churn_scores_run_id_rank", "run_id", "rank"),)

    run_id: Mapped[int] = mapped_column(
        ForeignKey("churn_runs.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    rank: Mapped[int]  # 1 is the highest probability
    probability: Mapped[float]
    plan: Mapped[str] = mapped_column(String(20))
    period_end: Mapped[datetime]
    # list price of the renewal; null for runs scored before it was kept
    period_price: Mapped[float | None]
    features: Mapped[dict[str, Any]] = mapped_column(JSONB)  # feature key → value
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
