"""Manually trigger a full fetch cycle for one source.

Bypasses the Celery queue — runs inline. Useful for developing fetchers or
for smoke-testing end-to-end without starting a worker.

Usage:
    python -m scripts.dev_fetch bbc
    python -m scripts.dev_fetch nhk --limit 3
"""

import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.errors import FetchError
from app.core.logging import configure_logging, get_logger
from app.core.utils import url_hash
from app.models import Article, Source
from app.models.base import Lang
from workers.fetchers.rss import RSSFetcher

configure_logging()
log = get_logger("dev_fetch")
settings = get_settings()


async def run(slug: str, limit: int) -> None:
    engine = create_async_engine(settings.db_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        source = (
            await db.execute(select(Source).where(Source.slug == slug))
        ).scalar_one_or_none()
        if source is None:
            log.error("source.not_found", slug=slug)
            return
        if source.fetcher != "rss":
            log.error("source.unsupported", slug=slug, fetcher=source.fetcher,
                       hint="dev_fetch currently only drives RSS")
            return

        fetcher = RSSFetcher(source.slug, source.feed_url, Lang(source.lang))

    urls = await fetcher.discover()
    log.info("discovered", slug=slug, count=len(urls))
    urls = urls[:limit]

    ok = 0
    skipped = 0
    errors = 0
    for url in urls:
        u_hash = url_hash(url)
        async with Session() as db:
            exists = await db.execute(select(Article.id).where(Article.url_hash == u_hash))
            if exists.scalar_one_or_none() is not None:
                skipped += 1
                log.info("skip.duplicate", url=url)
                continue

        try:
            doc = await fetcher.fetch_article(url)
        except FetchError as e:
            errors += 1
            log.warning("fetch.fail", url=url, error_class=type(e).__name__, error=str(e))
            continue

        async with Session() as db:
            stmt = (
                pg_insert(Article)
                .values(
                    source_id=source.id,
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
        ok += 1
        log.info("fetched", url=url, title=doc.title[:60])

    log.info("summary", slug=slug, ok=ok, skipped=skipped, errors=errors)
    await engine.dispose()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("slug")
    p.add_argument("--limit", type=int, default=5)
    args = p.parse_args()
    asyncio.run(run(args.slug, args.limit))
