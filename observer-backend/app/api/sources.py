"""Source management routes.

Endpoints:
  GET  /api/sources                       — list with health + cookie status
  POST /api/sources                       — create a new free RSS source
  GET  /api/sources/:slug                 — single source
  POST /api/sources/:slug/cookies         — import cookies (encrypted at rest)
"""

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUserId, SessionDep
from app.core.db import SessionLocal
from app.models.base import Lang
from app.schemas.base import APIModel
from app.schemas.source import SourceRead
from app.services import auth_capture_service, cookie_service, fetch_service, source_service

router = APIRouter(tags=["sources"])


# ─── schemas ────────────────────────────────────
class SourceCreate(APIModel):
    name: str
    feed_url: str
    lang: Lang
    region: str
    name_local: str | None = None
    slug: str | None = None


class CookieImportPayload(APIModel):
    cookies: list[dict]
    user_agent: str | None = None


class CookieImportResult(APIModel):
    ok: bool
    count: int
    expires_at: str | None = None
    slug: str


class RefreshSourceItem(APIModel):
    slug: str
    ok: int = 0
    skipped: int = 0
    errors: int = 0
    error_message: str | None = None


class RefreshResultPayload(APIModel):
    triggered: list[RefreshSourceItem]
    skipped_recent: list[str]
    total_new: int


# ─── routes ─────────────────────────────────────
@router.get("/sources", response_model=list[SourceRead])
async def list_sources(db: SessionDep, user_id: CurrentUserId) -> list[SourceRead]:
    rows = await source_service.list_sources(db, user_id=user_id)
    return [SourceRead.model_validate(r) for r in rows]


@router.post("/sources", response_model=SourceRead, status_code=201)
async def create_source(
    payload: SourceCreate,
    db: SessionDep,
    user_id: CurrentUserId,
) -> SourceRead:
    src = await source_service.create_rss_source(
        db,
        name=payload.name,
        feed_url=payload.feed_url,
        lang=payload.lang,
        region=payload.region,
        name_local=payload.name_local,
        slug=payload.slug,
    )
    rows = await source_service.list_sources(db, user_id=user_id)
    for r in rows:
        if r["slug"] == src.slug:
            return SourceRead.model_validate(r)
    raise HTTPException(status_code=500, detail="created source not found in listing")


@router.post("/sources/refresh", response_model=RefreshResultPayload)
async def refresh_sources(user_id: CurrentUserId) -> RefreshResultPayload:
    """Trigger a fetch across all eligible RSS sources (cooldown 5 min).
    Paywalled sources only run if the caller has valid cookies stored."""
    result = await fetch_service.refresh_eligible(
        SessionLocal, cooldown_minutes=5, user_id=user_id
    )
    return RefreshResultPayload(
        triggered=[
            RefreshSourceItem(
                slug=t.slug,
                ok=t.ok,
                skipped=t.skipped,
                errors=t.errors,
                error_message=t.error_message,
            )
            for t in result.triggered
        ],
        skipped_recent=result.skipped_recent,
        total_new=result.total_new,
    )


@router.get("/sources/{slug}", response_model=SourceRead)
async def get_source(slug: str, db: SessionDep, user_id: CurrentUserId) -> SourceRead:
    all_sources = await source_service.list_sources(db, user_id=user_id)
    for s in all_sources:
        if s["slug"] == slug:
            return SourceRead.model_validate(s)
    raise HTTPException(status_code=404, detail=f"source {slug!r} not found")


class AutoCaptureStart(APIModel):
    job_id: str


class AutoCaptureStatus(APIModel):
    job_id: str
    slug: str
    phase: str
    message: str
    started_at: str
    updated_at: str
    duration_ms: int
    error: str | None = None
    result: dict | None = None


@router.post(
    "/sources/{slug}/cookies/auto-start", response_model=AutoCaptureStart
)
async def start_auto_capture(
    slug: str, user_id: CurrentUserId
) -> AutoCaptureStart:
    """Launches a headed Chromium so the user can log in. Returns a jobId.
    Frontend polls /auto-status/{jobId} for progress."""
    job_id = auth_capture_service.start_capture(
        SessionLocal, user_id=user_id, slug=slug
    )
    return AutoCaptureStart(job_id=job_id)


@router.get(
    "/sources/{slug}/cookies/auto-status/{job_id}",
    response_model=AutoCaptureStatus,
)
async def auto_capture_status(
    slug: str,  # noqa: ARG001 — kept for URL clarity
    job_id: str,
    user_id: CurrentUserId,
) -> AutoCaptureStatus:
    state = auth_capture_service.get_status(job_id, user_id=user_id)
    return AutoCaptureStatus(**state.to_payload())


@router.post(
    "/sources/{slug}/cookies/auto-cancel/{job_id}",
    response_model=AutoCaptureStatus,
)
async def auto_capture_cancel(
    slug: str,  # noqa: ARG001
    job_id: str,
    user_id: CurrentUserId,
) -> AutoCaptureStatus:
    state = await auth_capture_service.cancel(job_id, user_id=user_id)
    return AutoCaptureStatus(**state.to_payload())


@router.post("/sources/{slug}/cookies", response_model=CookieImportResult)
async def save_cookies(
    slug: str,
    payload: CookieImportPayload,
    db: SessionDep,
    user_id: CurrentUserId,
) -> CookieImportResult:
    row = await cookie_service.save_cookies(
        db,
        user_id=user_id,
        source_slug=slug,
        cookies=payload.cookies,
        user_agent=payload.user_agent,
    )
    return CookieImportResult(
        ok=True,
        count=len(payload.cookies),
        expires_at=row.expires_at.isoformat() if row.expires_at else None,
        slug=slug,
    )
