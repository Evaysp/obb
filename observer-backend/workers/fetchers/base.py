"""BaseFetcher contract — all concrete fetchers implement this.

Per CONVENTIONS.md §6:
- Each source gets its own file; changes stay localized
- Errors classified via FetchError subclasses; BaseFetcher does NOT swallow them —
  caller (Celery task) decides retry policy based on the subclass
- rate_limit_per_min is a hint; actual limiting happens in the Celery task layer
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.models.base import Lang


@dataclass(slots=True)
class ArticleDoc:
    """Extracted article in a source-neutral shape."""

    url: str
    title: str
    summary: str
    content_html: str | None
    content_text: str | None
    author: str | None
    published_at: datetime
    lang: Lang
    lead_image_url: str | None
    reading_time_min: int | None


class BaseFetcher(ABC):
    """Abstract contract — implement `discover` and `fetch_article`."""

    slug: str
    lang: Lang
    rate_limit_per_min: int = 6
    needs_cookies: bool = False

    @abstractmethod
    async def discover(self) -> list[str]:
        """Return URLs to attempt this cycle. Raise TransientError on network blips."""

    @abstractmethod
    async def fetch_article(
        self,
        url: str,
        cookies: list[dict] | None = None,
    ) -> ArticleDoc:
        """Fetch + extract one article. Raise a FetchError subclass on failure."""
