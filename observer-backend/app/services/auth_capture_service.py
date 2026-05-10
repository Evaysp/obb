"""Browser-driven cookie capture for paywalled sources.

Click "Auto Import" on the cookies page → this service launches a headed
Chromium window via Playwright, navigates to the source's login URL, lets
the user authenticate (the user types credentials directly into the real
site — we never see them), then `context.cookies()` captures the session
including HttpOnly auth cookies and we store them encrypted via cookie_service.

Job state lives in-process (single-user dev mode). Frontend polls the
status endpoint every ~2s.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.services import cookie_service

if TYPE_CHECKING:
    pass

log = get_logger("auth_capture")


# ─── per-source login config ────────────────────
@dataclass
class LoginConfig:
    start_url: str
    success_url_re: re.Pattern[str]
    cookie_domain_substr: str  # filter cookies by domain to avoid grabbing unrelated ones
    timeout_ms: int = 300_000   # 5 minutes for the user to log in


LOGIN_CONFIGS: dict[str, LoginConfig] = {
    "nikkei": LoginConfig(
        start_url="https://id.nikkei.com/login/",
        # After login, Nikkei redirects to www.nikkei.com or my.nikkei.com (NOT id.nikkei.com)
        success_url_re=re.compile(
            r"^https?://(?:www|my|disclosure)\.nikkei\.com/(?!login).*"
        ),
        cookie_domain_substr="nikkei.com",
    ),
    # add ft / bloomberg / nikkei in future...
}


# ─── job model ──────────────────────────────────
JobPhase = str  # "pending" | "browser_open" | "waiting_login" | "saving" | "done" | "error" | "cancelled"


@dataclass
class JobState:
    job_id: str
    user_id: UUID
    slug: str
    phase: JobPhase
    message: str
    started_at: datetime
    updated_at: datetime
    error: str | None = None
    result: dict | None = None
    _task: asyncio.Task | None = field(default=None, repr=False)

    def to_payload(self) -> dict:
        return {
            "job_id": self.job_id,
            "slug": self.slug,
            "phase": self.phase,
            "message": self.message,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "duration_ms": int(
                (self.updated_at - self.started_at).total_seconds() * 1000
            ),
            "error": self.error,
            "result": self.result,
        }


JOBS: dict[str, JobState] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set(state: JobState, phase: JobPhase, message: str) -> None:
    state.phase = phase
    state.message = message
    state.updated_at = _now()
    log.info("auth_capture", job=state.job_id[:8], slug=state.slug, phase=phase, msg=message)


# ─── public API ─────────────────────────────────
class CaptureUnsupported(AppError):
    status_code = 400
    code = "capture_unsupported"


def start_capture(
    db_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
    slug: str,
) -> str:
    if slug not in LOGIN_CONFIGS:
        raise CaptureUnsupported(f"auto-import not configured for source {slug!r}")

    # Re-use a still-running job for the same (user, slug) instead of stacking
    for j in JOBS.values():
        if (
            j.user_id == user_id
            and j.slug == slug
            and j.phase in ("pending", "browser_open", "waiting_login", "saving")
        ):
            return j.job_id

    job_id = str(uuid.uuid4())
    state = JobState(
        job_id=job_id,
        user_id=user_id,
        slug=slug,
        phase="pending",
        message="queued",
        started_at=_now(),
        updated_at=_now(),
    )
    JOBS[job_id] = state
    state._task = asyncio.create_task(_run(db_factory, state))
    return job_id


def get_status(job_id: str, *, user_id: UUID) -> JobState:
    state = JOBS.get(job_id)
    if state is None:
        raise NotFoundError(f"job {job_id!r} not found")
    if state.user_id != user_id:
        raise NotFoundError(f"job {job_id!r} not found")
    return state


async def cancel(job_id: str, *, user_id: UUID) -> JobState:
    state = get_status(job_id, user_id=user_id)
    if state._task and not state._task.done():
        state._task.cancel()
    return state


# ─── runner ─────────────────────────────────────
async def _run(
    db_factory: async_sessionmaker[AsyncSession],
    state: JobState,
) -> None:
    cfg = LOGIN_CONFIGS[state.slug]
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        _set(state, "error", "playwright not installed")
        state.error = "pip install playwright && playwright install chromium"
        return

    try:
        _set(state, "browser_open", "launching chromium…")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                locale="ja-JP" if state.slug == "nikkei" else "en-US",
            )
            page = await context.new_page()

            _set(state, "waiting_login", f"please log in to {state.slug} in the browser window")
            await page.goto(cfg.start_url, wait_until="domcontentloaded")

            # Wait for redirect off the login domain. Polls internally.
            try:
                await page.wait_for_url(cfg.success_url_re, timeout=cfg.timeout_ms)
            except asyncio.CancelledError:
                _set(state, "cancelled", "cancelled by user")
                await browser.close()
                return
            except Exception as e:
                _set(state, "error", "login window timed out")
                state.error = (
                    f"didn't reach the post-login URL within {cfg.timeout_ms // 1000}s. "
                    f"({type(e).__name__})"
                )
                await browser.close()
                return

            _set(state, "saving", "login detected, capturing cookies…")
            raw = await context.cookies()
            await browser.close()

        # Filter to relevant domain only
        filtered: list[dict] = []
        for c in raw:
            domain = c.get("domain") or ""
            if cfg.cookie_domain_substr in domain:
                filtered.append(_to_browser_format(c))

        if not filtered:
            _set(state, "error", "logged in but no cookies captured")
            state.error = (
                f"no cookies for *{cfg.cookie_domain_substr} were present in the session"
            )
            return

        async with db_factory() as db:
            row = await cookie_service.save_cookies(
                db,
                user_id=state.user_id,
                source_slug=state.slug,
                cookies=filtered,
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
            )

        state.result = {
            "cookie_count": len(filtered),
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }
        _set(state, "done", f"saved {len(filtered)} cookies")

    except asyncio.CancelledError:
        _set(state, "cancelled", "cancelled")
        raise
    except Exception as e:
        log.warning("auth_capture.fail", job=state.job_id[:8], err=str(e))
        _set(state, "error", "capture failed")
        state.error = f"{type(e).__name__}: {e}"


def _to_browser_format(c: dict) -> dict:
    """Convert Playwright cookie dict → the browser-export shape cookie_service
    expects (with `expirationDate` instead of `expires`)."""
    out = {
        "name": c["name"],
        "value": c["value"],
        "domain": c.get("domain", ""),
        "path": c.get("path", "/"),
        "secure": bool(c.get("secure", False)),
        "httpOnly": bool(c.get("httpOnly", False)),
    }
    expires = c.get("expires", -1)
    if isinstance(expires, (int, float)) and expires > 0:
        out["expirationDate"] = float(expires)
    return out
