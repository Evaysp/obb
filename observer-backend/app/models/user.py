"""User, Subscription, UserCookie.

User is placeholder-simple — a dev user seeded at boot. Real auth per CONVENTIONS.md §7
lands in a later phase. UserCookie and Subscription schemas are complete so the scrapers
and notifier workers can be built against stable tables.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CookieStatus, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)


class UserCookie(Base, TimestampMixin):
    __tablename__ = "user_cookies"
    __table_args__ = (UniqueConstraint("user_id", "source_id", name="uniq_user_cookies_user_src"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    cookies_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    status: Mapped[CookieStatus] = mapped_column(
        Enum(CookieStatus, name="cookie_status"),
        nullable=False,
        default=CookieStatus.ok,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Subscription(Base, TimestampMixin):
    """User → Entity tracking."""

    __tablename__ = "subscriptions"
    __table_args__ = (PrimaryKeyConstraint("user_id", "entity_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notify_channels: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list
    )
    muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
