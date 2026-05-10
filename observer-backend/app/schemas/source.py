from datetime import datetime

from app.models.base import CookieStatus, Lang, SourceKind, SourceTier
from app.schemas.base import APIModel


class SourceRead(APIModel):
    slug: str
    name: str
    name_local: str | None = None
    lang: Lang
    region: str
    kind: SourceKind
    tier: SourceTier
    feed_url: str | None = None
    needs_cookies: bool
    enabled: bool
    last_fetched_at: datetime | None = None
    # computed fields filled in at the service layer
    article_count_24h: int = 0
    cookie_status: CookieStatus | None = None
    cookie_expires_at: datetime | None = None
