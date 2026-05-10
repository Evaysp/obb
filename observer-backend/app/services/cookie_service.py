"""Cookie vault — encrypted cookie storage per (user, source).

Per CONVENTIONS.md §7:
- Cookies encrypted with Fernet at the API boundary, never plaintext in DB
- UPSERT keyed on (user_id, source_id) — one cookie blob per user per source
- expires_at derived from the earliest cookie expiration in the bundle
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.security import decrypt_cookies, encrypt_cookies
from app.models import Source, UserCookie
from app.models.base import CookieStatus

log = get_logger("cookie_service")


async def save_cookies(
    db: AsyncSession,
    *,
    user_id: UUID,
    source_slug: str,
    cookies: list[dict],
    user_agent: str | None,
) -> UserCookie:
    """Validate, encrypt, UPSERT. Returns the saved row."""
    if not isinstance(cookies, list) or not cookies:
        raise ValidationError("cookies must be a non-empty array")
    for i, c in enumerate(cookies):
        if not isinstance(c, dict):
            raise ValidationError(f"cookie at index {i} is not an object")
        if not isinstance(c.get("name"), str) or not isinstance(c.get("value"), str):
            raise ValidationError(f"cookie at index {i} missing name/value")

    src = (
        await db.execute(select(Source).where(Source.slug == source_slug))
    ).scalar_one_or_none()
    if src is None:
        raise NotFoundError(f"source {source_slug!r} not found")

    blob = encrypt_cookies(cookies)
    expires_at = _earliest_expiration(cookies)
    now = datetime.now(timezone.utc)

    existing = (
        await db.execute(
            select(UserCookie)
            .where(UserCookie.user_id == user_id)
            .where(UserCookie.source_id == src.id)
        )
    ).scalar_one_or_none()

    if existing is None:
        row = UserCookie(
            user_id=user_id,
            source_id=src.id,
            cookies_encrypted=blob,
            user_agent=user_agent,
            status=CookieStatus.ok,
            expires_at=expires_at,
            last_ok_at=now,
        )
        db.add(row)
    else:
        existing.cookies_encrypted = blob
        existing.user_agent = user_agent
        existing.status = CookieStatus.ok
        existing.expires_at = expires_at
        existing.last_ok_at = now
        row = existing

    await db.commit()
    await db.refresh(row)
    return row


async def get_cookies_for_source(
    db: AsyncSession, *, user_id: UUID, source_id: int
) -> tuple[list[dict] | None, str | None]:
    """Return (cookies, user_agent) for a (user, source) — or (None, None)
    if missing, expired, or undecryptable."""
    row = (
        await db.execute(
            select(UserCookie)
            .where(UserCookie.user_id == user_id)
            .where(UserCookie.source_id == source_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return None, None
    if row.status in (CookieStatus.expired, CookieStatus.missing):
        return None, None
    try:
        cookies = decrypt_cookies(row.cookies_encrypted)
    except AuthError as e:
        log.warning("cookie.decrypt_fail", source_id=source_id, err=str(e))
        return None, None
    return cookies, row.user_agent


async def mark_cookies_stale(
    db: AsyncSession, *, user_id: UUID, source_id: int
) -> None:
    """Called when an authenticated fetch fails — flips status to 'expired'."""
    row = (
        await db.execute(
            select(UserCookie)
            .where(UserCookie.user_id == user_id)
            .where(UserCookie.source_id == source_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return
    row.status = CookieStatus.expired
    await db.commit()


def _earliest_expiration(cookies: list[dict]) -> datetime | None:
    """The bundle expires when the first cookie does. Session cookies (no
    expirationDate) are ignored — they have no fixed lifetime."""
    soonest: float | None = None
    for c in cookies:
        ed = c.get("expirationDate") or c.get("expires")
        if not isinstance(ed, (int, float)):
            continue
        if soonest is None or ed < soonest:
            soonest = float(ed)
    if soonest is None:
        return None
    return datetime.fromtimestamp(soonest, tz=timezone.utc)
