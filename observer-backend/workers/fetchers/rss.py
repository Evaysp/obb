"""Generic RSS fetcher — Atom and RSS, free sources without auth.

Per CONVENTIONS.md §6:
- Don't trust RSS <description> for full content — it's often truncated
- Fetch the article page with httpx, hand HTML to trafilatura via extract.py
- Raise the right FetchError subclass so retry policy is correct
"""

from __future__ import annotations

from datetime import datetime, timezone

import feedparser
import httpx
from dateutil import parser as dateparser

from app.core.config import get_settings
from app.core.errors import (
    BlockedError,
    ExtractionError,
    FetchNotFoundError,
    TransientError,
)
from app.core.logging import get_logger
from app.models.base import Lang
from workers.extract import extract
from workers.fetchers.base import ArticleDoc, BaseFetcher

log = get_logger("fetcher.rss")


class RSSFetcher(BaseFetcher):
    """Drive-by RSS fetcher. One instance per configured source."""

    def __init__(self, slug: str, feed_url: str, lang: Lang) -> None:
        self.slug = slug
        self.lang = lang
        self.feed_url = feed_url

    async def discover(self) -> list[str]:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": settings.fetch_user_agent},
                timeout=settings.fetch_timeout_seconds,
                follow_redirects=True,
            ) as client:
                r = await client.get(self.feed_url)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 429):
                raise BlockedError(f"feed blocked: {e.response.status_code}") from e
            raise TransientError(f"feed {self.feed_url} status {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise TransientError(f"feed {self.feed_url} request failed: {e}") from e

        parsed = feedparser.parse(r.content)
        return [e.link for e in parsed.entries if getattr(e, "link", None)]

    async def fetch_article(
        self,
        url: str,
        cookies: list[dict] | None = None,
    ) -> ArticleDoc:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": settings.fetch_user_agent},
                timeout=settings.fetch_timeout_seconds,
                follow_redirects=True,
            ) as client:
                r = await client.get(url)
        except httpx.RequestError as e:
            raise TransientError(f"request failed: {e}") from e

        if r.status_code == 404:
            raise FetchNotFoundError(f"404 at {url}")
        if r.status_code in (403, 429):
            raise BlockedError(f"blocked {r.status_code} at {url}")
        if r.status_code >= 500:
            raise TransientError(f"upstream {r.status_code}")
        if r.status_code >= 400:
            raise ExtractionError(f"unexpected status {r.status_code}")

        doc = extract(r.text, url)
        if not doc or not doc.get("title"):
            raise ExtractionError(f"extraction returned nothing for {url}")

        return ArticleDoc(
            url=url,
            title=doc["title"],
            summary=doc["summary"],
            content_html=doc["content_html"],
            content_text=doc["content_text"],
            author=doc["author"],
            published_at=_parse_date(doc["published_at"]),
            lang=self.lang,
            lead_image_url=doc["lead_image_url"],
            reading_time_min=doc["reading_time_min"],
        )


def _parse_date(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        dt = dateparser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
