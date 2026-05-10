"""Per-user key/value settings — used for AI provider keys + custom prompt.

Two value columns so the same row schema covers both kinds of data:
- value_text:      plaintext (e.g. default_provider, custom_prompt)
- value_encrypted: Fernet-encrypted bytes (e.g. provider api keys)
"""

import uuid

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uniq_app_settings_user_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
