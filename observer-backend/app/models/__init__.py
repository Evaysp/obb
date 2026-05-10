"""Model registry — importing this module registers every mapper with Base.metadata.

Alembic's env.py imports from here so autogenerate sees all tables.
"""

from app.models.article import Article
from app.models.base import (
    Base,
    CookieStatus,
    EntityKind,
    Lang,
    SoftDeleteMixin,
    SourceKind,
    SourceTier,
    TimestampMixin,
)
from app.models.entity import ArticleEntity, Entity
from app.models.setting import AppSetting
from app.models.source import Source
from app.models.user import Subscription, User, UserCookie

__all__ = [
    "AppSetting",
    "Article",
    "ArticleEntity",
    "Base",
    "CookieStatus",
    "Entity",
    "EntityKind",
    "Lang",
    "SoftDeleteMixin",
    "Source",
    "SourceKind",
    "SourceTier",
    "Subscription",
    "TimestampMixin",
    "User",
    "UserCookie",
]
