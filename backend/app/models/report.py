from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAt


class Report(CreatedAt, Base):
    """A titled, frozen copy of sections of a dataset: its analytics, or an approved decision
    (a retention plan, a content portfolio) with the parameters it was made with."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("analysts.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), server_default="analytics")  # report_kind
    title: Mapped[str] = mapped_column(String(200))
    sections: Mapped[list[str]] = mapped_column(JSONB)  # section keys, canonical order
    # dataset name, as_of, timezone and the section payloads at creation time
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # what a decision was made with
