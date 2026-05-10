"""Entity tracking and subscription routes.

Endpoints:
  GET    /api/entities                    — list entities, with subscribed flag
  POST   /api/subscriptions               — subscribe to an entity
  DELETE /api/subscriptions/:entity_slug  — unsubscribe
"""

from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.entity import EntityRead, SubscriptionCreate
from app.services import entity_service

router = APIRouter(tags=["entities"])


@router.get("/entities", response_model=list[EntityRead])
async def list_entities(
    db: SessionDep,
    user_id: CurrentUserId,
    subscribed_only: bool = False,
) -> list[EntityRead]:
    rows = await entity_service.list_entities(
        db, user_id=user_id, subscribed_only=subscribed_only
    )
    return [EntityRead.model_validate(r) for r in rows]


@router.post("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    payload: SubscriptionCreate,
    db: SessionDep,
    user_id: CurrentUserId,
) -> None:
    await entity_service.subscribe(
        db,
        user_id=user_id,
        entity_slug=payload.entity_slug,
        notify_channels=payload.notify_channels,
    )


@router.delete("/subscriptions/{entity_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    entity_slug: str,
    db: SessionDep,
    user_id: CurrentUserId,
) -> None:
    await entity_service.unsubscribe(db, user_id=user_id, entity_slug=entity_slug)
