"""Database engine and session management.

Per CONVENTIONS.md §4:
- AsyncSession only (no sync mixing in the web path)
- Eager loading explicit at the query site — no lazy load ambushes
- Workers rebuild engine after fork (see workers/celery_app.py)
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_settings = get_settings()

engine: AsyncEngine = create_async_engine(
    _settings.db_url,
    echo=_settings.db_echo,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a session, commits on clean exit, rolls back on error."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
