from datetime import date, datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAt


class Dataset(CreatedAt, Base):
    """An imported dataset. Immutable once `ready`: analytics are computed at import time."""

    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("owner_id", "sha256"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("analysts.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    schema_version: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    # pending | importing | ready | failed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    as_of: Mapped[date | None]
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Kyiv")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # e.g. ["descriptive", "retention", "content"]
    capabilities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    row_counts: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class DatasetAnalytics(Base):
    """Precomputed descriptive analytics, one JSON payload per section."""

    __tablename__ = "dataset_analytics"

    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True
    )
    section: Mapped[str] = mapped_column(String(40), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(server_default=func.now())
