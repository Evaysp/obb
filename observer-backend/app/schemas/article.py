from datetime import datetime

from pydantic import Field

from app.models.base import Lang
from app.schemas.base import APIModel


class ArticleListItem(APIModel):
    """Compact shape used in feed, source detail, entity detail."""

    id: int
    source_slug: str
    url: str
    title: str
    author: str | None = None
    published_at: datetime
    lang: Lang
    summary: str
    lead_image_url: str | None = None
    reading_time_min: int | None = None
    entities: list[str] = Field(default_factory=list)


class ArticleDetail(ArticleListItem):
    """Full shape for the detail page — includes cleaned HTML body."""

    content_html: str | None = None
    fetched_at: datetime


class Page[T](APIModel):
    """Generic page envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int
