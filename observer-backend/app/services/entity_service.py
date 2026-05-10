"""Entity + subscription logic."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models import ArticleEntity, Entity, Subscription


async def list_entities(
    db: AsyncSession,
    *,
    user_id: UUID,
    subscribed_only: bool = False,
) -> list[dict]:
    subs = await _subscribed_entity_ids(db, user_id)

    stmt = select(Entity).order_by(Entity.canonical_name)
    if subscribed_only:
        if not subs:
            return []
        stmt = stmt.where(Entity.id.in_(subs))
    entities = (await db.execute(stmt)).scalars().all()

    counts = await _article_counts_7d(db, [e.id for e in entities])

    return [
        {
            "slug": e.slug,
            "canonical_name": e.canonical_name,
            "name_local": e.name_local,
            "kind": e.kind,
            "aliases": e.aliases,
            "description": e.description,
            "image_url": e.image_url,
            "article_count_7d": counts.get(e.id, 0),
            "subscribed": e.id in subs,
        }
        for e in entities
    ]


async def subscribe(
    db: AsyncSession,
    *,
    user_id: UUID,
    entity_slug: str,
    notify_channels: list[str],
) -> None:
    entity = await _get_entity_by_slug(db, entity_slug)
    stmt = (
        pg_insert(Subscription)
        .values(
            user_id=user_id,
            entity_id=entity.id,
            notify_channels=notify_channels or ["webpush"],
            muted=False,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "entity_id"],
            set_={"notify_channels": notify_channels or ["webpush"], "muted": False},
        )
    )
    await db.execute(stmt)


async def unsubscribe(db: AsyncSession, *, user_id: UUID, entity_slug: str) -> None:
    entity = await _get_entity_by_slug(db, entity_slug)
    result = await db.execute(
        delete(Subscription)
        .where(Subscription.user_id == user_id)
        .where(Subscription.entity_id == entity.id)
    )
    if result.rowcount == 0:
        raise ConflictError(f"not subscribed to {entity_slug}")


async def _get_entity_by_slug(db: AsyncSession, slug: str) -> Entity:
    entity = (
        await db.execute(select(Entity).where(Entity.slug == slug))
    ).scalar_one_or_none()
    if entity is None:
        raise NotFoundError(f"entity {slug!r} not found")
    return entity


async def _subscribed_entity_ids(db: AsyncSession, user_id: UUID) -> set[int]:
    stmt = select(Subscription.entity_id).where(Subscription.user_id == user_id)
    rows = (await db.execute(stmt)).scalars().all()
    return set(rows)


async def _article_counts_7d(db: AsyncSession, entity_ids: list[int]) -> dict[int, int]:
    if not entity_ids:
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    from app.models import Article

    stmt = (
        select(ArticleEntity.entity_id, func.count(ArticleEntity.article_id))
        .join(Article, Article.id == ArticleEntity.article_id)
        .where(ArticleEntity.entity_id.in_(entity_ids))
        .where(Article.published_at >= cutoff)
        .where(Article.deleted_at.is_(None))
        .group_by(ArticleEntity.entity_id)
    )
    return dict((await db.execute(stmt)).all())
