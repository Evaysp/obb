"""SQLAlchemy declarative base and shared mixins.

Per CONVENTIONS.md §5:
- SQLAlchemy 2.x Mapped[...] / mapped_column syntax only
- All tables get created_at + updated_at TIMESTAMPTZ
- Soft delete via nullable deleted_at
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


# ─── shared enum types ──────────────────────────
class Lang(StrEnum):
    en = "en"
    zh = "zh"
    ja = "ja"


class SourceKind(StrEnum):
    rss = "rss"
    html = "html"
    api = "api"


class SourceTier(StrEnum):
    free = "free"
    paywall = "paywall"


class CookieStatus(StrEnum):
    missing = "missing"
    ok = "ok"
    expiring = "expiring"
    expired = "expired"


class EntityKind(StrEnum):
    person = "person"
    company = "company"
