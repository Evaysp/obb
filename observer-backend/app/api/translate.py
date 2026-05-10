"""Translation endpoint — bulk-translate article titles + summaries."""

from fastapi import APIRouter

from app.api.deps import CurrentUserId, SessionDep
from app.core.redis_client import redis_client
from app.schemas.base import APIModel
from app.services import translation_service

router = APIRouter(tags=["translate"], prefix="/translate")


class TranslateBatchRequest(APIModel):
    article_ids: list[int]
    target_lang: str = "zh"


class TranslationItem(APIModel):
    title: str
    summary: str
    cached: bool = False
    error: str | None = None


class TranslateBatchResponse(APIModel):
    target_lang: str
    translations: dict[int, TranslationItem]


@router.post("/articles", response_model=TranslateBatchResponse)
async def translate_articles(
    payload: TranslateBatchRequest,
    db: SessionDep,
    user_id: CurrentUserId,
) -> TranslateBatchResponse:
    raw = await translation_service.translate_articles(
        redis_client,
        db,
        user_id=user_id,
        article_ids=payload.article_ids,
        target_lang=payload.target_lang,
    )
    items = {
        aid: TranslationItem(
            title=v.get("title", ""),
            summary=v.get("summary", ""),
            cached=bool(v.get("cached", False)),
            error=v.get("error"),
        )
        for aid, v in raw.items()
    }
    return TranslateBatchResponse(
        target_lang=payload.target_lang, translations=items
    )


class TranslateOneRequest(APIModel):
    target_lang: str = "zh"


class TranslateOneResponse(APIModel):
    id: int
    title: str
    summary: str
    content_html: str
    cached: bool = False


class TranslateBlocksRequest(APIModel):
    texts: list[str]
    target_lang: str = "zh"


class TranslateBlocksResponse(APIModel):
    target_lang: str
    translations: list[str | None]  # None = model failed for that block
    cached: list[bool]               # parallel to translations


@router.post("/blocks", response_model=TranslateBlocksResponse)
async def translate_blocks(
    payload: TranslateBlocksRequest,
    db: SessionDep,
    user_id: CurrentUserId,
) -> TranslateBlocksResponse:
    """Block-level translation. Each text (typically one paragraph's HTML)
    is translated and cached individually by content hash. Used by the
    article reader for incremental, bilingual display."""
    translations, cached = await translation_service.translate_blocks(
        redis_client,
        db,
        user_id=user_id,
        texts=payload.texts,
        target_lang=payload.target_lang,
    )
    return TranslateBlocksResponse(
        target_lang=payload.target_lang,
        translations=translations,
        cached=cached,
    )


@router.post("/article/{article_id}", response_model=TranslateOneResponse)
async def translate_one_article(
    article_id: int,
    payload: TranslateOneRequest,
    db: SessionDep,
    user_id: CurrentUserId,
) -> TranslateOneResponse:
    """Full-article translation (title + summary + content_html). Used by the
    detail page. Cached per (article, target_lang) for 24h."""
    res = await translation_service.translate_one_full(
        redis_client,
        db,
        user_id=user_id,
        article_id=article_id,
        target_lang=payload.target_lang,
    )
    return TranslateOneResponse(
        id=res["id"],
        title=res["title"],
        summary=res["summary"],
        content_html=res.get("contentHtml", ""),
        cached=bool(res.get("cached", False)),
    )
