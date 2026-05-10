"""Feed and article routes.

Endpoints:
  GET /api/feed        — paginated list with filters
  GET /api/articles/:id — full article detail
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.models.base import Lang
from app.schemas.article import ArticleDetail, ArticleListItem, Page
from app.services import feed_service

router = APIRouter(tags=["feed"])


@router.get("/feed", response_model=Page[ArticleListItem])
async def get_feed(
    db: SessionDep,
    lang: Lang | None = None,
    region: Annotated[str | None, Query(max_length=8)] = None,
    tier: Literal["all", "free", "paywall"] = "all",
    source: Annotated[str | None, Query(alias="source", max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ArticleListItem]:
    items, total = await feed_service.list_feed(
        db,
        lang=lang,
        region=region,
        tier=tier,
        source_slug=source,
        limit=limit,
        offset=offset,
    )
    return Page[ArticleListItem](
        items=[ArticleListItem.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/articles/{article_id}", response_model=ArticleDetail)
async def get_article(article_id: int, db: SessionDep) -> ArticleDetail:
    detail = await feed_service.get_article_detail(db, article_id)
    return ArticleDetail.model_validate(detail)
