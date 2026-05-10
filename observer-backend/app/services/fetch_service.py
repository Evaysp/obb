"""Inline fetch service — runs RSS pulls without Celery.

Wired to the `POST /api/sources/refresh` endpoint so a page reload can
trigger a refresh end-to-end. Per-source cooldown prevents hammering
external feeds when the user reloads repeatedly.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import FetchAuthError, FetchError
from app.core.logging import get_logger
from app.core.utils import url_hash
from app.models import Article, Source
from app.models.base import Lang
from app.services import cookie_service
from workers.fetchers.base import BaseFetcher
from workers.fetchers.ft import FTFetcher
from workers.fetchers.nikkei import NikkeiFetcher
from workers.fetchers.rss import RSSFetcher

log = get_logger("fetch_service")


@dataclass
class SourceResult:
    slug: str
    ok: int = 0
    skipped: int = 0
    errors: int = 0
    error_message: str | None = None


@dataclass
class RefreshResult:
    triggered: list[SourceResult] = field(default_factory=list)
    skipped_recent: list[str] = field(default_factory=list)
    total_new: int = 0


def _build_fetcher(
    source: Source,
    *,
    cookies: list[dict] | None = None,
    user_agent: str | None = None,
) -> BaseFetcher:
    if source.fetcher == "rss":
        if not source.feed_url:
            raise NotImplementedError(f"rss source {source.slug} has no feed_url")
        return RSSFetcher(source.slug, source.feed_url, Lang(source.lang))
    if source.fetcher == "nikkei":
        return NikkeiFetcher(
            source.slug,
            Lang(source.lang),
            cookies=cookies,
            user_agent=user_agent,
            feed_url=source.feed_url,
        )
    if source.fetcher == "ft":
        return FTFetcher(
            source.slug,
            Lang(source.lang),
            cookies=cookies,
            user_agent=user_agent,
            feed_url=source.feed_url,
        )
    raise NotImplementedError(
        f"fetcher {source.fetcher!r} not supported inline (source={source.slug})"
    )


async def _fetch_one(
    session_factory: async_sessionmaker[AsyncSession],
    source_id: int,
    *,
    limit: int,
    user_id: UUID | None = None,
) -> SourceResult:
    """Pull URLs for one source, fetch up to `limit` new articles, insert.

    For paywalled sources (`needs_cookies=True`), pulls + decrypts the user's
    cookie row and passes it into the fetcher. If the cookies are missing or
    auth fails, marks the row stale and returns an error.
    """
    async with session_factory() as db:
        source = (
            await db.execute(select(Source).where(Source.id == source_id))
        ).scalar_one_or_none()
        if source is None:
            return SourceResult(slug=f"id={source_id}", errors=1, error_message="source missing")
        slug = source.slug

        cookies = None
        ua = None
        if source.needs_cookies:
            if user_id is None:
                return SourceResult(
                    slug=slug, errors=1, error_message="paywall source requires user context"
                )
            cookies, ua = await cookie_service.get_cookies_for_source(
                db, user_id=user_id, source_id=source.id
            )
            if cookies is None:
                return SourceResult(
                    slug=slug,
                    errors=1,
                    error_message="no valid cookies — import via /sources/{slug}/cookies",
                )

        try:
            fetcher = _build_fetcher(source, cookies=cookies, user_agent=ua)
        except NotImplementedError as e:
            return SourceResult(slug=slug, errors=1, error_message=str(e))

    result = SourceResult(slug=slug)

    try:
        urls = await fetcher.discover()
    except FetchError as e:
        log.warning("fetch.discover_fail", slug=slug, err=str(e))
        async with session_factory() as db:
            src = (await db.execute(select(Source).where(Source.id == source_id))).scalar_one()
            src.last_error = str(e)[:512]
            src.last_fetched_at = datetime.now(timezone.utc)
            await db.commit()
        result.errors = 1
        result.error_message = str(e)
        return result

    urls = urls[:limit]

    for u in urls:
        u_hash = url_hash(u)
        async with session_factory() as db:
            exists = await db.execute(
                select(Article.id).where(Article.url_hash == u_hash)
            )
            if exists.scalar_one_or_none() is not None:
                result.skipped += 1
                continue
        try:
            doc = await fetcher.fetch_article(u)
        except FetchAuthError as e:
            # cookies stale → flip status, abort the rest of this source's run
            log.warning("fetch.auth_fail", slug=slug, url=u, err=str(e))
            if source.needs_cookies and user_id is not None:
                async with session_factory() as db:
                    await cookie_service.mark_cookies_stale(
                        db, user_id=user_id, source_id=source_id
                    )
            result.errors += 1
            result.error_message = "auth failed — cookies stale, re-import"
            break
        except FetchError as e:
            log.info("fetch.article_fail", slug=slug, url=u, err=str(e))
            result.errors += 1
            continue
        async with session_factory() as db:
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
        result.ok += 1

    async with session_factory() as db:
        src = (await db.execute(select(Source).where(Source.id == source_id))).scalar_one()
        src.last_fetched_at = datetime.now(timezone.utc)
        src.last_error = None if result.errors == 0 else f"{result.errors} article fetch error(s)"
        try:
            await db.commit()
        except SQLAlchemyError as e:
            log.warning("fetch.last_fetched_update_fail", slug=slug, err=str(e))
            await db.rollback()

    log.info(
        "fetch.done",
        slug=slug,
        ok=result.ok,
        skipped=result.skipped,
        errors=result.errors,
    )
    return result


async def refresh_eligible(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    cooldown_minutes: int = 5,
    per_source_limit: int = 10,
    user_id: UUID | None = None,
) -> RefreshResult:
    """Find enabled sources past their cooldown and fetch in parallel.
    Paywalled sources only run if the user has valid cookies stored."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)

    async with session_factory() as db:
        rows = (
            await db.execute(
                select(Source).where(
                    Source.enabled.is_(True),
                    Source.fetcher.in_(("rss", "nikkei", "ft")),
                )
            )
        ).scalars().all()

    eligible_ids: list[int] = []
    skipped_recent: list[str] = []
    skipped_no_cookie: list[str] = []
    async with session_factory() as db:
        for s in rows:
            if s.last_fetched_at and s.last_fetched_at >= cutoff:
                skipped_recent.append(s.slug)
                continue
            if s.needs_cookies:
                if user_id is None:
                    skipped_no_cookie.append(s.slug)
                    continue
                cookies, _ = await cookie_service.get_cookies_for_source(
                    db, user_id=user_id, source_id=s.id
                )
                if cookies is None:
                    skipped_no_cookie.append(s.slug)
                    continue
            eligible_ids.append(s.id)

    if not eligible_ids:
        return RefreshResult(skipped_recent=skipped_recent + skipped_no_cookie)

    log.info(
        "refresh.start",
        eligible=len(eligible_ids),
        skipped=len(skipped_recent),
        no_cookie=len(skipped_no_cookie),
    )
    results = await asyncio.gather(
        *[
            _fetch_one(session_factory, sid, limit=per_source_limit, user_id=user_id)
            for sid in eligible_ids
        ],
        return_exceptions=True,
    )

    out = RefreshResult(skipped_recent=skipped_recent + skipped_no_cookie)
    for r in results:
        if isinstance(r, Exception):
            log.warning("refresh.task_exc", err=str(r))
            out.triggered.append(SourceResult(slug="?", errors=1, error_message=str(r)))
            continue
        out.triggered.append(r)
        out.total_new += r.ok
    log.info("refresh.done", total_new=out.total_new, sources=len(out.triggered))
    return out
