# Single image used for both API and worker. Command is overridden per service
# in docker-compose.yml.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps: gcc/libffi for cryptography wheels on non-x86, libxml2 for lxml/trafilatura,
# curl for healthchecks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libffi-dev libxml2-dev libxslt1-dev curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching.
COPY pyproject.toml /app/
RUN pip install --upgrade pip setuptools wheel \
 && pip install "fastapi>=0.115,<0.116" "uvicorn[standard]>=0.32,<0.33" "httpx>=0.27,<0.28" \
                "sqlalchemy[asyncio]>=2.0.35,<2.1" "asyncpg>=0.29,<0.30" "alembic>=1.13,<1.14" \
                "pgvector>=0.3,<0.4" "pydantic>=2.9,<3" "pydantic-settings>=2.5,<3" \
                "python-dotenv>=1.0,<2" "cryptography>=43,<44" "passlib[argon2]>=1.7.4,<2" \
                "argon2-cffi>=23.1,<24" "celery[redis]>=5.4,<6" "feedparser>=6.0.11,<7" \
                "trafilatura>=1.12,<2" "beautifulsoup4>=4.12,<5" "bleach>=6.1,<7" \
                "python-dateutil>=2.9,<3" "structlog>=24.4,<25" "rich>=13.9,<14" \
                "aiolimiter>=1.1,<2"

# App source
COPY . /app

# Non-root user for the worker (Playwright/chromium in later phases won't run as root).
RUN useradd -m -u 1000 observer && chown -R observer:observer /app
USER observer

EXPOSE 8000
