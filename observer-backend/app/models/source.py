"""Source — a news outlet configuration (RSS feed or HTML crawl target)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Lang, SourceKind, SourceTier, TimestampMixin


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_local: Mapped[str | None] = mapped_column(String(128), nullable=True)

    lang: Mapped[Lang] = mapped_column(Enum(Lang, name="lang"), nullable=False)
    region: Mapped[str] = mapped_column(String(8), nullable=False)  # JP, CN, HK, UK, US
    kind: Mapped[SourceKind] = mapped_column(Enum(SourceKind, name="source_kind"), nullable=False)
    tier: Mapped[SourceTier] = mapped_column(
        Enum(SourceTier, name="source_tier"), nullable=False, default=SourceTier.free
    )

    feed_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    fetcher: Mapped[str] = mapped_column(String(128), nullable=False)  # python module path
    schedule_cron: Mapped[str] = mapped_column(String(64), nullable=False, default="*/15 * * * *")

    needs_cookies: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Source slug={self.slug} enabled={self.enabled}>"
