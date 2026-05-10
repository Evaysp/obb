"""FastAPI dependencies — keep thin, business logic lives in services.

Per CONVENTIONS.md §4 and §7:
- AsyncSession yielded from db.get_session
- Real auth deferred; dev mode returns a hardcoded user. When auth lands, replace
  the body of `current_user` with JWT / session validation — callers don't change.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AuthError
from app.models import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def current_user(db: SessionDep) -> User:
    """Returns the single dev user. Swap implementation when real auth lands."""
    settings = get_settings()
    stmt = select(User).where(User.id == settings.dev_user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise AuthError("dev user not seeded — run `python -m scripts.seed`")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def current_user_id(user: CurrentUser) -> UUID:
    return user.id


CurrentUserId = Annotated[UUID, Depends(current_user_id)]
