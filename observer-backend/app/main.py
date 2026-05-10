"""FastAPI application entry point.

Per CONVENTIONS.md §4 and §12:
- Structured logging configured before anything else
- AppError hierarchy caught by a single exception handler → uniform JSON error envelope
- Three health endpoints: livez (process alive), readyz (deps reachable), healthz (full)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import ai, entities, feed, settings as settings_api, sources, translate
from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app.startup", env=settings.app_env, debug=settings.app_debug)
    yield
    await engine.dispose()
    log.info("app.shutdown")


app = FastAPI(
    title="Observer API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_dev else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── error handler ──────────────────────────────
@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    log.warning(
        "app.error",
        code=exc.code,
        status=exc.status_code,
        path=request.url.path,
        message=str(exc),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )


# ─── health ─────────────────────────────────────
@app.get("/livez", include_in_schema=False)
async def livez() -> dict:
    return {"ok": True}


@app.get("/readyz", include_in_schema=False)
async def readyz() -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        log.error("readyz.db_fail", error=str(e))
        return JSONResponse(status_code=503, content={"ok": False, "db": False})
    return {"ok": True, "db": True}


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict:
    return await readyz()


# ─── routers ────────────────────────────────────
app.include_router(feed.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(entities.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(translate.router, prefix="/api")
