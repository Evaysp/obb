"""Celery app for background work.

Per CONVENTIONS.md §11:
- Redis broker, no result backend (we don't .get() results)
- Tasks only take IDs as arguments (never ORM objects across process boundary)
- DB engine created lazily per worker process (not forked from parent)
- pool=solo so Playwright + asyncio later play nicely; prefork would clash
"""

from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()

celery_app = Celery(
    "observer",
    broker=settings.redis_url,
    backend=None,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_routes={
        "workers.tasks.fetch_source": {"queue": "fetch"},
        "workers.tasks.fetch_article": {"queue": "fetch"},
    },
    task_default_retry_delay=60,
    task_time_limit=300,
    task_soft_time_limit=240,
    broker_connection_retry_on_startup=True,
)
