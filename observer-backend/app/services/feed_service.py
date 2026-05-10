"""Feed querying logic — keeps the API layer thin per CONVENTIONS.md §4."""

from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Article, ArticleEntity, Entity, Source
from app.models.base import Lang, SourceTier

TierFilter = Literal["all", "free", "paywall"]


async def list_feed(
    db: AsyncSession,
    *,
    lang: Lang | None = None,
    region: str | None = None,
    tier: TierFilter = "all",
    source_slug: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (items, total). Items are dicts shaped for ArticleListItem."""

    base: Select = (
        select(Article, Source.slug.label("source_slug"))
        .join(Source, Article.source_id == Source.id)
        .where(Article.deleted_at.is_(None))
        .where(Source.enabled.is_(True))
    )

    if lang is not None:
        base = base.where(Article.lang == lang)
    if region is not None:
        base = base.where(Source.region == region)
    if tier == "free":
        base = base.where(Source.tier == SourceTier.free)
    elif tier == "paywall":
        base = base.where(Source.tier == SourceTier.paywall)
    if source_slug is not None:
        base = base.where(Source.slug == source_slug)

    total_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    rows_stmt = base.order_by(Article.published_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(rows_stmt)).all()

    article_ids = [row.Article.id for row in rows]
    entities_by_article = await _load_entity_slugs(db, article_ids)

    items = [
        _to_list_item(row.Article, row.source_slug, entities_by_article.get(row.Article.id, []))
        for row in rows
    ]
    return items, total


async def get_article_detail(db: AsyncSession, article_id: int) -> dict:
    stmt = (
        select(Article, Source.slug.label("source_slug"))
        .join(Source, Article.source_id == Source.id)
        .where(Article.id == article_id)
        .where(Article.deleted_at.is_(None))
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise NotFoundError(f"article {article_id} not found")

    entities_by_article = await _load_entity_slugs(db, [row.Article.id])
    entity_slugs = entities_by_article.get(row.Article.id, [])

    base = _to_list_item(row.Article, row.source_slug, entity_slugs)
    base["content_html"] = row.Article.content_html
    base["fetched_at"] = row.Article.fetched_at
    return base


async def _load_entity_slugs(
    db: AsyncSession, article_ids: list[int]
) -> dict[int, list[str]]:
    if not article_ids:
        return {}
    stmt = (
        select(ArticleEntity.article_id, Entity.slug)
        .join(Entity, Entity.id == ArticleEntity.entity_id)
        .where(ArticleEntity.article_id.in_(article_ids))
        .order_by(ArticleEntity.article_id, Entity.slug)
    )
    rows = (await db.execute(stmt)).all()
    out: dict[int, list[str]] = {}
    for article_id, slug in rows:
        out.setdefault(article_id, []).append(slug)
    return out


def _to_list_item(article: Article, source_slug: str, entity_slugs: list[str]) -> dict:
    return {
        "id": article.id,
        "source_slug": source_slug,
        "url": article.url,
        "title": article.title,
        "author": article.author,
        "published_at": article.published_at,
        "lang": article.lang,
        "summary": article.summary,
        "lead_image_url": article.lead_image_url,
        "reading_time_min": article.reading_time_min,
        "entities": entity_slugs,
    }


def hours_ago(h: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=h)
