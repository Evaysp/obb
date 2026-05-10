"""Async Redis client — used for short-lived caches (e.g. translations).

The `redis` package is pulled in via `celery[redis]` so no new dep needed.
We never block on Redis: helpers degrade gracefully if Redis is unreachable
(translation cache simply misses and we re-run the LLM).
"""

from __future__ import annotations

from redis import asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("redis")
_settings = get_settings()

# decode_responses=True → strings instead of bytes; we only store JSON text.
redis_client: aioredis.Redis = aioredis.from_url(
    _settings.redis_url,
    decode_responses=True,
    socket_timeout=2.0,
    socket_connect_timeout=2.0,
)
