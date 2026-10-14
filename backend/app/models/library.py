"""Library data of an imported dataset; tables mirror dataset format v2 one to one.

Every row belongs to a dataset (`ON DELETE CASCADE`). Natural ids from the file (user_id,
book_id, loan_id, ...) are unique per dataset. There are no foreign keys between library tables:
the importer validates references in bulk, which keeps COPY fast.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

Money = Numeric(10, 2, asdecimal=False)


def _dataset_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)


def _dataset_ref() -> Mapped[int]:
    return mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))


class LibUser(Base):
    __tablename__ = "lib_users"

    dataset_id: Mapped[int] = _dataset_fk()
    user_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    registered_at: Mapped[datetime]
    age_range: Mapped[str | None] = mapped_column(String(20))
    education: Mapped[str | None] = mapped_column(String(40))
    language_pref: Mapped[str | None] = mapped_column(String(10))
    email_opt_in: Mapped[bool | None]
    interests: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # v1 snapshot fields


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (Index("ix_books_dataset_id_genre", "dataset_id", "genre"),)

    dataset_id: Mapped[int] = _dataset_fk()
    book_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)
    genre: Mapped[str] = mapped_column(String(40))
    language: Mapped[str | None] = mapped_column(String(10))
    pages: Mapped[int | None]
    first_year: Mapped[int | None] = mapped_column(SmallInteger)
    copies: Mapped[int | None]  # v1 datasets have no licence data


class SubscriptionPeriod(Base):
    __tablename__ = "subscription_periods"
    __table_args__ = (
        Index("ix_subscription_periods_dataset_id_period_end", "dataset_id", "period_end"),
        Index(
            "ix_subscription_periods_dataset_id_user_id", "dataset_id", "user_id", "period_start"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset_id: Mapped[int] = _dataset_ref()
    user_id: Mapped[str] = mapped_column(String(40))
    plan: Mapped[str] = mapped_column(String(20))
    period_start: Mapped[datetime]
    period_end: Mapped[datetime]
    list_price: Mapped[float] = mapped_column(Money)
    paid_amount: Mapped[float] = mapped_column(Money)
    discount_pct: Mapped[float | None]
    outcome: Mapped[str | None] = mapped_column(
        String(20)
    )  # open|renewed|churned|converted|expired


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        Index("ix_loans_dataset_id_user_id", "dataset_id", "user_id", "borrowed_at"),
        Index("ix_loans_dataset_id_book_id", "dataset_id", "book_id", "borrowed_at"),
    )

    dataset_id: Mapped[int] = _dataset_fk()
    loan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40))
    book_id: Mapped[str] = mapped_column(String(60))
    borrowed_at: Mapped[datetime]
    returned_at: Mapped[datetime | None]
    completed: Mapped[bool | None]
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    via_hold: Mapped[bool] = mapped_column(default=False)


class ReadingSession(Base):
    __tablename__ = "reading_sessions"
    __table_args__ = (
        Index("ix_reading_sessions_dataset_id_user_id", "dataset_id", "user_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset_id: Mapped[int] = _dataset_ref()
    user_id: Mapped[str] = mapped_column(String(40))
    book_id: Mapped[str] = mapped_column(String(60))
    started_at: Mapped[datetime]
    minutes: Mapped[int]
    pages: Mapped[int]
    device: Mapped[str | None] = mapped_column(String(30))


class Search(Base):
    __tablename__ = "searches"
    __table_args__ = (
        Index("ix_searches_dataset_id_searched_at", "dataset_id", "searched_at"),
        Index(
            "ix_searches_zero_results",
            "dataset_id",
            "searched_at",
            postgresql_where=text("results_count = 0"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset_id: Mapped[int] = _dataset_ref()
    user_id: Mapped[str] = mapped_column(String(40))
    searched_at: Mapped[datetime]
    query: Mapped[str] = mapped_column(Text)
    results_count: Mapped[int | None]  # v1 datasets do not record it


class Hold(Base):
    __tablename__ = "holds"
    __table_args__ = (Index("ix_holds_dataset_id_book_id", "dataset_id", "book_id", "placed_at"),)

    dataset_id: Mapped[int] = _dataset_fk()
    hold_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40))
    book_id: Mapped[str] = mapped_column(String(60))
    placed_at: Mapped[datetime]
    resolved_at: Mapped[datetime | None]
    outcome: Mapped[str] = mapped_column(String(20))  # open|fulfilled|lapsed|cancelled


class Campaign(Base):
    __tablename__ = "campaigns"

    dataset_id: Mapped[int] = _dataset_fk()
    campaign_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    design: Mapped[str] = mapped_column(String(40))
    arms: Mapped[list[str]] = mapped_column(ARRAY(String(40)))


class CampaignAssignment(Base):
    __tablename__ = "campaign_assignments"
    __table_args__ = (
        Index(
            "uq_campaign_assignments_member", "dataset_id", "campaign_id", "user_id", unique=True
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset_id: Mapped[int] = _dataset_ref()
    campaign_id: Mapped[str] = mapped_column(String(60))
    user_id: Mapped[str] = mapped_column(String(40))
    assigned_at: Mapped[datetime]
    arm: Mapped[str] = mapped_column(String(40))
    delivered: Mapped[bool]
    discount_pct: Mapped[float]
    target_period_end: Mapped[datetime]


class CandidateTitle(Base):
    __tablename__ = "candidate_titles"

    dataset_id: Mapped[int] = _dataset_fk()
    candidate_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)
    genre: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(10))
    pages: Mapped[int]
    first_year: Mapped[int | None] = mapped_column(SmallInteger)
    license_cost: Mapped[float] = mapped_column(Money)
    offered_at: Mapped[datetime]
