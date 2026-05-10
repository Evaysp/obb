"""Celery tasks.

Per CONVENTIONS.md §6 and §11:
- FetchError subclasses drive retry policy (AuthError/NotFoundError never retry)
- Tasks take IDs, not ORM objects
- Each task is idempotent: ON CONFLICT DO NOTHING on article insert
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.errors import (
    BlockedError,
    ExtractionError,
    FetchAuthError,
    FetchNotFoundError,
    TransientError,
)
from app.core.logging import get_logger
from app.core.utils import url_hash
from app.models import Article, Source
from app.models.base import Lang
from workers.celery_app import celery_app
from workers.fetchers.rss import RSSFetcher

log = get_logger("worker.tasks")

# Per-worker engine (built once, reused across task invocations in the same process).
_settings = get_settings()
_engine = create_async_engine(_settings.db_url, pool_pre_ping=True, pool_size=5)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)


def _run(coro):
    """Run an async coroutine from the sync Celery task body."""
    return asyncio.run(coro)


@celery_app.task(
    name="workers.tasks.fetch_source",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def fetch_source(self, source_id: int) -> dict:
    """Discover URLs for one source and enqueue per-article tasks."""
    try:
        return _run(_fetch_source(source_id))
    except (BlockedError, TransientError) as exc:
        log.warning("fetch_source.retry", source_id=source_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _fetch_source(source_id: int) -> dict:
    async with _SessionLocal() as db:
        source = (
            await db.execute(select(Source).where(Source.id == source_id))
        ).scalar_one()

        if not source.enabled:
            return {"skipped": True, "reason": "disabled"}

        fetcher = _build_fetcher(source)
        urls = await fetcher.discover()
        log.info("fetch_source.discovered", slug=source.slug, count=len(urls))

        source.last_fetched_at = datetime.now(timezone.utc)
        await db.commit()

    for url in urls:
        fetch_article.apply_async(
            args=[source_id, url],
            queue="fetch",
            rate_limit=f"{_rate_for(source)}/m",
        )

    return {"slug": source.slug, "queued": len(urls)}


@celery_app.task(
    name="workers.tasks.fetch_article",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def fetch_article(self, source_id: int, url: str) -> dict:
    try:
        return _run(_fetch_article(source_id, url))
    except FetchNotFoundError:
        return {"skipped": True, "reason": "not_found", "url": url}
    except FetchAuthError as exc:
        log.warning("fetch_article.auth_fail", url=url, error=str(exc))
        return {"skipped": True, "reason": "auth", "url": url}
    except ExtractionError as exc:
        log.warning("fetch_article.extract_fail", url=url, error=str(exc))
        return {"skipped": True, "reason": "extract", "url": url}
    except (BlockedError, TransientError) as exc:
        log.warning("fetch_article.retry", url=url, error=str(exc))
        raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))


async def _fetch_article(source_id: int, url: str) -> dict:
    u_hash = url_hash(url)

    async with _SessionLocal() as db:
        exists = await db.execute(
            select(Article.id).where(Article.url_hash == u_hash)
        )
        if exists.scalar_one_or_none() is not None:
            return {"skipped": True, "reason": "duplicate", "url": url}

        source = (
            await db.execute(select(Source).where(Source.id == source_id))
        ).scalar_one()
        fetcher = _build_fetcher(source)

    doc = await fetcher.fetch_article(url)

    async with _SessionLocal() as db:
        stmt = (
            pg_insert(Article)
            .values(
                source_id=source_id,
                url=doc.url,
                url_hash=u_hash,
                title=doc.title,
                author=doc.author,
                published_at=doc.published_at,
                fetched_at=datetime.now(timezone.utc),
                lang=doc.lang,
                summary=doc.summary,
                content_html=doc.content_html,
                content_text=doc.content_text,
                lead_image_url=doc.lead_image_url,
                reading_time_min=doc.reading_time_min,
            )
            .on_conflict_do_nothing(index_elements=["url_hash"])
        )
        await db.execute(stmt)
        await db.commit()

    log.info("fetch_article.ok", url=url, title=doc.title[:60])
    return {"ok": True, "url": url, "title": doc.title}


def _build_fetcher(source: Source):
    """Dispatch to a concrete fetcher. For now only RSS is wired."""
    if source.fetcher == "rss":
        if not source.feed_url:
            raise ValueError(f"source {source.slug} is RSS but has no feed_url")
        return RSSFetcher(source.slug, source.feed_url, Lang(source.lang))
    raise NotImplementedError(
        f"fetcher {source.fetcher!r} not implemented yet (source={source.slug})"
    )


def _rate_for(source: Source) -> int:
    return _settings.fetch_default_rate_per_min
