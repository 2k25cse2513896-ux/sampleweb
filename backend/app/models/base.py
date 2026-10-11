"""Declarative base and timestamp columns shared by most tables."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Timezone-aware UTC clock used as a default for created_at."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """All tables inherit this so Alembic and create_all see one metadata object."""

    pass


class TimestampMixin:
    """created_at is set once. updated_at changes on every ORM flush."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
