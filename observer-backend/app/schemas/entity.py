from app.models.base import EntityKind
from app.schemas.base import APIModel


class EntityRead(APIModel):
    slug: str
    canonical_name: str
    name_local: str | None = None
    kind: EntityKind
    aliases: list[str]
    description: str | None = None
    image_url: str | None = None
    article_count_7d: int = 0
    subscribed: bool = False


class SubscriptionCreate(APIModel):
    entity_slug: str
    notify_channels: list[str] = []
