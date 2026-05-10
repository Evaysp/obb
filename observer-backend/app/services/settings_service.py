"""User-scoped key/value settings.

Conventions:
- API keys (and any future secrets) live in `value_encrypted` (Fernet).
- Plain prefs (default provider, custom prompt) live in `value_text`.
- Reads return a typed `Settings` snapshot — no decrypted secrets in API responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import _fernet  # internal but stable; same key as cookies
from app.models import AppSetting

PROVIDERS = ("anthropic", "openai", "deepseek", "minimax")
PROVIDER_KEYS = {p: f"ai.api_key.{p}" for p in PROVIDERS}
PROVIDER_MODELS = {p: f"ai.model.{p}" for p in PROVIDERS}
PROVIDER_ENDPOINTS = {p: f"ai.endpoint.{p}" for p in PROVIDERS}
KEY_DEFAULT_PROVIDER = "ai.default_provider"
KEY_CUSTOM_PROMPT = "ai.custom_prompt"


@dataclass
class Settings:
    default_provider: str = "anthropic"
    custom_prompt: str | None = None
    configured_providers: list[str] = field(default_factory=list)
    model_overrides: dict[str, str] = field(default_factory=dict)
    endpoint_overrides: dict[str, str] = field(default_factory=dict)


def _enc(value: str) -> bytes:
    return _fernet.encrypt(value.encode("utf-8"))


def _dec(blob: bytes) -> str:
    return _fernet.decrypt(blob).decode("utf-8")


async def _all_for(db: AsyncSession, user_id: UUID) -> dict[str, AppSetting]:
    rows = (
        await db.execute(select(AppSetting).where(AppSetting.user_id == user_id))
    ).scalars().all()
    return {r.key: r for r in rows}


async def read_settings(db: AsyncSession, user_id: UUID) -> Settings:
    bag = await _all_for(db, user_id)
    out = Settings()
    if (r := bag.get(KEY_DEFAULT_PROVIDER)) and r.value_text:
        out.default_provider = r.value_text
    if (r := bag.get(KEY_CUSTOM_PROMPT)) and r.value_text:
        out.custom_prompt = r.value_text
    out.configured_providers = sorted(
        p for p, k in PROVIDER_KEYS.items() if k in bag and bag[k].value_encrypted
    )
    for p, mk in PROVIDER_MODELS.items():
        r = bag.get(mk)
        if r and r.value_text and r.value_text.strip():
            out.model_overrides[p] = r.value_text.strip()
    for p, ek in PROVIDER_ENDPOINTS.items():
        r = bag.get(ek)
        if r and r.value_text and r.value_text.strip():
            out.endpoint_overrides[p] = r.value_text.strip()
    return out


async def get_provider_model(
    db: AsyncSession, user_id: UUID, provider: str
) -> str | None:
    return await _get_text(db, user_id, PROVIDER_MODELS.get(provider))


async def get_provider_endpoint(
    db: AsyncSession, user_id: UUID, provider: str
) -> str | None:
    return await _get_text(db, user_id, PROVIDER_ENDPOINTS.get(provider))


async def _get_text(
    db: AsyncSession, user_id: UUID, key: str | None
) -> str | None:
    if not key:
        return None
    row = (
        await db.execute(
            select(AppSetting)
            .where(AppSetting.user_id == user_id)
            .where(AppSetting.key == key)
        )
    ).scalar_one_or_none()
    if row is None or not row.value_text or not row.value_text.strip():
        return None
    return row.value_text.strip()


async def get_provider_key(
    db: AsyncSession, user_id: UUID, provider: str
) -> str | None:
    if provider not in PROVIDERS:
        return None
    row = (
        await db.execute(
            select(AppSetting)
            .where(AppSetting.user_id == user_id)
            .where(AppSetting.key == PROVIDER_KEYS[provider])
        )
    ).scalar_one_or_none()
    if row is None or row.value_encrypted is None:
        return None
    return _dec(row.value_encrypted)


async def _upsert_text(
    db: AsyncSession, user_id: UUID, key: str, value: str | None
) -> None:
    row = (
        await db.execute(
            select(AppSetting).where(AppSetting.user_id == user_id, AppSetting.key == key)
        )
    ).scalar_one_or_none()
    if row is None:
        if value is None:
            return
        db.add(AppSetting(user_id=user_id, key=key, value_text=value))
    else:
        if value is None:
            await db.delete(row)
        else:
            row.value_text = value


async def _upsert_secret(
    db: AsyncSession, user_id: UUID, key: str, plain_value: str | None
) -> None:
    row = (
        await db.execute(
            select(AppSetting).where(AppSetting.user_id == user_id, AppSetting.key == key)
        )
    ).scalar_one_or_none()
    if plain_value is None:
        if row is not None:
            await db.delete(row)
        return
    blob = _enc(plain_value)
    if row is None:
        db.add(AppSetting(user_id=user_id, key=key, value_encrypted=blob))
    else:
        row.value_encrypted = blob


async def update_settings(
    db: AsyncSession,
    user_id: UUID,
    *,
    default_provider: str | None = None,
    custom_prompt: str | None = None,
    clear_custom_prompt: bool = False,
    api_keys: dict[str, str | None] | None = None,
    models: dict[str, str | None] | None = None,
    endpoints: dict[str, str | None] | None = None,
) -> Settings:
    """Partial update. Pass only the fields you want to change.

    api_keys / models: { provider: "value" } sets, "" / None clears.
    """
    if default_provider is not None:
        if default_provider not in PROVIDERS:
            raise ValueError(f"unknown provider {default_provider!r}")
        await _upsert_text(db, user_id, KEY_DEFAULT_PROVIDER, default_provider)

    if clear_custom_prompt:
        await _upsert_text(db, user_id, KEY_CUSTOM_PROMPT, None)
    elif custom_prompt is not None:
        await _upsert_text(db, user_id, KEY_CUSTOM_PROMPT, custom_prompt)

    if api_keys:
        for provider, raw in api_keys.items():
            if provider not in PROVIDERS:
                continue
            normalized = None if raw is None or raw.strip() == "" else raw.strip()
            await _upsert_secret(db, user_id, PROVIDER_KEYS[provider], normalized)

    if models:
        for provider, raw in models.items():
            if provider not in PROVIDERS:
                continue
            normalized = None if raw is None or raw.strip() == "" else raw.strip()
            await _upsert_text(db, user_id, PROVIDER_MODELS[provider], normalized)

    if endpoints:
        for provider, raw in endpoints.items():
            if provider not in PROVIDERS:
                continue
            normalized = None if raw is None or raw.strip() == "" else raw.strip()
            await _upsert_text(db, user_id, PROVIDER_ENDPOINTS[provider], normalized)

    await db.commit()
    return await read_settings(db, user_id)
