"""Source listing + creation logic."""

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

import feedparser
import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import Article, Source, UserCookie
from app.models.base import CookieStatus, Lang, SourceKind, SourceTier


async def list_sources(db: AsyncSession, *, user_id: UUID) -> list[dict]:
    sources = (await db.execute(select(Source).order_by(Source.name))).scalars().all()

    counts = await _article_counts_24h(db, [s.id for s in sources])
    cookies_by_source = await _user_cookies_by_source(db, user_id, [s.id for s in sources])

    out = []
    for s in sources:
        cookie = cookies_by_source.get(s.id)
        out.append(
            {
                "slug": s.slug,
                "name": s.name,
                "name_local": s.name_local,
                "lang": s.lang,
                "region": s.region,
                "kind": s.kind,
                "tier": s.tier,
                "feed_url": s.feed_url,
                "needs_cookies": s.needs_cookies,
                "enabled": s.enabled,
                "last_fetched_at": s.last_fetched_at,
                "article_count_24h": counts.get(s.id, 0),
                "cookie_status": _cookie_status_for(s, cookie),
                "cookie_expires_at": cookie.expires_at if cookie else None,
            }
        )
    return out


async def get_source(db: AsyncSession, slug: str) -> Source:
    stmt = select(Source).where(Source.slug == slug)
    source = (await db.execute(stmt)).scalar_one_or_none()
    if source is None:
        raise NotFoundError(f"source {slug!r} not found")
    return source


# ─── source creation ──────────────────────────────
SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = SLUG_RE.sub("-", s).strip("-")
    return s[:64] or "source"


async def create_rss_source(
    db: AsyncSession,
    *,
    name: str,
    feed_url: str,
    lang: Lang,
    region: str,
    name_local: str | None = None,
    slug: str | None = None,
) -> Source:
    """Validate the feed by fetching + parsing it, then INSERT."""
    name = name.strip()
    feed_url = feed_url.strip()
    region = region.strip().upper()

    if not name:
        raise ValidationError("name is required")
    if not feed_url.startswith(("http://", "https://")):
        raise ValidationError("feedUrl must be http(s)")
    if not 1 <= len(region) <= 8:
        raise ValidationError("region must be 1–8 chars (e.g. UK, JP, INTL)")

    final_slug = slugify(slug) if slug else slugify(name)

    # ── Probe the feed: fetchable + parseable + has entries ──
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            timeout=settings.fetch_timeout_seconds,
            headers={"User-Agent": settings.fetch_user_agent},
            follow_redirects=True,
        ) as client:
            resp = await client.get(feed_url)
    except httpx.HTTPError as e:
        raise ValidationError(f"feed unreachable: {e}") from e

    if resp.status_code >= 400:
        raise ValidationError(f"feed returned {resp.status_code}")

    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        raise ValidationError("feed could not be parsed as RSS/Atom")
    if not parsed.entries:
        raise ValidationError("feed has no entries")

    src = Source(
        slug=final_slug,
        name=name,
        name_local=name_local.strip() if name_local else None,
        lang=lang,
        region=region,
        kind=SourceKind.rss,
        tier=SourceTier.free,
        feed_url=feed_url,
        fetcher="rss",
        schedule_cron="*/15 * * * *",
        needs_cookies=False,
        enabled=True,
    )
    db.add(src)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise ConflictError(f"slug {final_slug!r} already exists") from e
    await db.refresh(src)
    return src


async def _article_counts_24h(db: AsyncSession, source_ids: list[int]) -> dict[int, int]:
    if not source_ids:
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    stmt = (
        select(Article.source_id, func.count(Article.id))
        .where(Article.source_id.in_(source_ids))
        .where(Article.published_at >= cutoff)
        .where(Article.deleted_at.is_(None))
        .group_by(Article.source_id)
    )
    return dict((await db.execute(stmt)).all())


async def _user_cookies_by_source(
    db: AsyncSession, user_id: UUID, source_ids: list[int]
) -> dict[int, UserCookie]:
    if not source_ids:
        return {}
    stmt = (
        select(UserCookie)
        .where(UserCookie.user_id == user_id)
        .where(UserCookie.source_id.in_(source_ids))
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {c.source_id: c for c in rows}


def _cookie_status_for(source: Source, cookie: UserCookie | None) -> CookieStatus | None:
    if not source.needs_cookies:
        return None
    if cookie is None:
        return CookieStatus.missing
    return cookie.status
