"""Entity (person / company) and its many-to-many link to Article.

Per CONVENTIONS.md §8:
- canonical identity anchored to Wikidata QID
- aliases stored as JSONB for fast in-memory Aho-Corasick load at worker startup
- article_entities is the NER output table; `confidence` supports future re-ranking
"""

from sqlalchemy import CHAR, Enum, Float, ForeignKey, Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, EntityKind, TimestampMixin


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)

    canonical_name: Mapped[str] = mapped_column(String(256), nullable=False)
    name_local: Mapped[str | None] = mapped_column(String(256), nullable=True)
    kind: Mapped[EntityKind] = mapped_column(Enum(EntityKind, name="entity_kind"), nullable=False)

    wikidata_qid: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class ArticleEntity(Base):
    __tablename__ = "article_entities"
    __table_args__ = (PrimaryKeyConstraint("article_id", "entity_id"),)

    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
