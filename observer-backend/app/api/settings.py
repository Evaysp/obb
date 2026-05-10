"""User settings — AI provider keys + custom prompt."""

from fastapi import APIRouter

from app.api.deps import CurrentUserId, SessionDep
from app.schemas.base import APIModel
from app.services import settings_service

router = APIRouter(tags=["settings"], prefix="/settings")


class SettingsRead(APIModel):
    default_provider: str
    custom_prompt: str | None = None
    configured_providers: list[str]
    model_overrides: dict[str, str]
    endpoint_overrides: dict[str, str]
    default_models: dict[str, str]
    default_endpoints: dict[str, str]
    default_prompt: str


class SettingsUpdate(APIModel):
    default_provider: str | None = None
    custom_prompt: str | None = None
    clear_custom_prompt: bool = False
    api_keys: dict[str, str | None] | None = None
    models: dict[str, str | None] | None = None
    endpoints: dict[str, str | None] | None = None


def _to_read(s: settings_service.Settings) -> SettingsRead:
    from app.services.ai_service import DEFAULT_ENDPOINTS, DEFAULT_MODELS, DEFAULT_PROMPT

    return SettingsRead(
        default_provider=s.default_provider,
        custom_prompt=s.custom_prompt,
        configured_providers=s.configured_providers,
        model_overrides=s.model_overrides,
        endpoint_overrides=s.endpoint_overrides,
        default_models=DEFAULT_MODELS,
        default_endpoints=DEFAULT_ENDPOINTS,
        default_prompt=DEFAULT_PROMPT,
    )


@router.get("", response_model=SettingsRead)
async def get_settings(db: SessionDep, user_id: CurrentUserId) -> SettingsRead:
    s = await settings_service.read_settings(db, user_id)
    return _to_read(s)


@router.put("", response_model=SettingsRead)
async def put_settings(
    payload: SettingsUpdate,
    db: SessionDep,
    user_id: CurrentUserId,
) -> SettingsRead:
    s = await settings_service.update_settings(
        db,
        user_id,
        default_provider=payload.default_provider,
        custom_prompt=payload.custom_prompt,
        clear_custom_prompt=payload.clear_custom_prompt,
        api_keys=payload.api_keys,
        models=payload.models,
        endpoints=payload.endpoints,
    )
    return _to_read(s)
