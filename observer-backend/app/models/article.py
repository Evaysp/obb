"""Article — a single ingested story from any source."""

from datetime import datetime

from sqlalchemy import (
    CHAR,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Lang, SoftDeleteMixin, TimestampMixin
from app.models.source import Source


class Article(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "articles"
    __table_args__ = (
        Index("idx_articles_published_at", "published_at"),
        Index("idx_articles_source_published", "source_id", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[Source] = relationship(lazy="noload")

    # URL identity — hash is the unique constraint because URLs are long / have variable suffixes.
    # See app/core/utils.canonicalize_url for the canonical form.
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    url_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    lang: Mapped[Lang] = mapped_column(Enum(Lang, name="lang"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    lead_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    reading_time_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # content_hash for cross-source dedup later (Week 10+).
    content_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Article id={self.id} title={self.title[:40]!r}>"
