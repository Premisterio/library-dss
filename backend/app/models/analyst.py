from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAt


class Analyst(CreatedAt, Base):
    """A user of the DSS (librarian / analyst)."""

    __tablename__ = "analysts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lower-cased
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="analyst")  # analyst | admin
    # Bumped on logout / password change: every token carrying an older version is rejected.
    token_version: Mapped[int] = mapped_column(default=0)
