"""AI summarization endpoint."""

from fastapi import APIRouter

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.base import APIModel
from app.services import ai_service

router = APIRouter(tags=["ai"], prefix="/ai")


class SummarizeRequest(APIModel):
    provider: str | None = None
    model: str | None = None
    custom_prompt: str | None = None
    hours: int = 24


class SummarizeResponse(APIModel):
    summary: str
    provider: str
    model: str
    article_count: int
    used_custom_prompt: bool


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    payload: SummarizeRequest,
    db: SessionDep,
    user_id: CurrentUserId,
) -> SummarizeResponse:
    r = await ai_service.summarize_today(
        db,
        user_id=user_id,
        provider=payload.provider,
        model=payload.model,
        custom_prompt=payload.custom_prompt,
        hours=payload.hours,
    )
    return SummarizeResponse(
        summary=r.summary,
        provider=r.provider,
        model=r.model,
        article_count=r.article_count,
        used_custom_prompt=r.used_custom_prompt,
    )
