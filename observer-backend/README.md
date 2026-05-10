# Observer backend

FastAPI + Celery + Postgres stack for the Observer personal news aggregator.
Pairs with the `news-aggregator/` frontend — `docker compose up` gives you a
backend at `http://localhost:8000` that the frontend can point at with one env
change.

## Stack

| Layer | Choice |
|---|---|
| Web | FastAPI 0.115 + Uvicorn |
| ORM | SQLAlchemy 2.x async + asyncpg |
| DB | Postgres 16 |
| Migrations | Alembic |
| Queue | Celery 5 + Redis 7 |
| Fetch | httpx + feedparser + trafilatura + bleach |
| Logs | structlog (JSON in prod, rich in dev) |
| Config | pydantic-settings |

## Layout

```
observer-backend/
├── app/
│   ├── main.py                 FastAPI app
│   ├── core/                   config, db, security, errors, logging, utils
│   ├── models/                 SQLAlchemy 2.x models (1 file / aggregate)
│   ├── schemas/                pydantic I/O (camelCase on the wire)
│   ├── services/               business logic — no HTTP concerns
│   └── api/                    route handlers — thin, delegate to services
├── workers/
│   ├── celery_app.py           Celery config
│   ├── tasks.py                fetch_source + fetch_article
│   ├── extract.py              trafilatura + bleach pipeline
│   └── fetchers/
│       ├── base.py             BaseFetcher ABC + ArticleDoc
│       └── rss.py              generic RSS fetcher (free sources)
├── alembic/                    migrations (0001_initial.py creates all tables)
├── scripts/
│   ├── seed.py                 dev user + sources + entities
│   └── dev_fetch.py            manual fetch trigger for one source
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

Companion document: `/CONVENTIONS.md` (in the frontend repo) — read first if
you're making non-trivial changes.

## Quickstart

```bash
# 1. bring up db + redis + api + worker
docker compose up --build

# 2. in another terminal, fetch a few articles right now (don't wait for cron)
docker compose exec worker python -m scripts.dev_fetch bbc --limit 5
docker compose exec worker python -m scripts.dev_fetch nhk --limit 5

# 3. hit the API
curl http://localhost:8000/api/feed | jq .
curl http://localhost:8000/api/sources | jq .
open http://localhost:8000/docs   # OpenAPI UI
```

Migrations + seed run automatically on `api` startup. If you need to reset:

```bash
docker compose down -v      # wipes the db volume
docker compose up --build
```

## Running without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env         # adjust DB_URL and REDIS_URL to your local services
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

In a second terminal:

```bash
celery -A workers.celery_app.celery_app worker --loglevel=info --pool=solo --queues=default,fetch
```

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/feed` | Paginated article list with `lang`, `region`, `tier`, `source`, `limit`, `offset` filters |
| GET | `/api/articles/{id}` | Full article with cleaned HTML body |
| GET | `/api/sources` | All sources with 24h article counts and cookie status |
| GET | `/api/sources/{slug}` | One source |
| POST | `/api/sources/{slug}/cookies` | **501 for now** — cookie vault lands in phase 2 |
| GET | `/api/entities?subscribedOnly=true` | Tracked entities with 7-day mention counts |
| POST | `/api/subscriptions` | Subscribe to an entity |
| DELETE | `/api/subscriptions/{entitySlug}` | Unsubscribe |
| GET | `/livez` / `/readyz` / `/healthz` | Health probes |

All response bodies are camelCase (pydantic `alias_generator=to_camel`) so the
frontend's TypeScript types match without conversion.

## Connecting the frontend

The frontend currently reads from `lib/mock-data.ts`. To point it at this
backend:

1. Add `NEXT_PUBLIC_API_URL=http://localhost:8000` to the frontend's `.env.local`.
2. Create `frontend/lib/api.ts` with `fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`)`.
3. Replace the imports from `@/lib/mock-data` with fetch calls (per page, per
   route — the shape of the data returned matches exactly).

## What's real, what's stubbed

**Real and working end-to-end:**
- RSS ingestion → extraction → DB → API → frontend
- Feed filtering (language, region, tier, source)
- Article detail pages
- Entity list with subscription toggle
- Source management with health status
- Migrations, seeding, logging, error handling
- Celery queues with classification-driven retry (per CONVENTIONS §6)

**Stubbed — wired but not implemented yet:**
- **Auth**: returns hardcoded dev user from `DEV_USER_ID`. Real JWT/session lives in phase 2.
- **Cookie import**: endpoint returns 501. Fernet encryption utilities are ready in `app/core/security.py`, the DB table is ready — only the route body is stubbed.
- **Celery Beat**: no scheduled trigger yet. Use `dev_fetch` CLI or call `fetch_source.delay(source_id)` from a shell.

**Deferred to later phases:**
- Playwright fetchers for paywall sites (phase 2, weeks 4–6)
- spaCy NER + entity extraction task (phase 3, weeks 7–9)
- Meilisearch integration (phase 3)
- pgvector embeddings + cross-source dedup (phase 4, week 10+)
- Web Push notifier worker (phase 3)

## Adding a new RSS source

```bash
docker compose exec db psql -U observer -d observer
```

```sql
INSERT INTO sources (slug, name, lang, region, kind, tier, fetcher, feed_url,
                     needs_cookies, enabled, schedule_cron)
VALUES ('guardian', 'The Guardian', 'en', 'UK', 'rss', 'free', 'rss',
        'https://www.theguardian.com/world/rss', false, true, '*/10 * * * *');
```

Then trigger a fetch:

```bash
docker compose exec worker python -m scripts.dev_fetch guardian
```

## Adding a new paywall source (phase 2)

1. Create `workers/fetchers/{slug}.py` implementing `BaseFetcher`.
2. Use `app.core.security.decrypt_cookies` to read stored cookies.
3. Register it in `workers/tasks.py::_build_fetcher`.
4. Add an INSERT in `scripts/seed.py` with `fetcher='{slug}'`, `needs_cookies=true`.

Each fetcher is one self-contained file. That's deliberate (CONVENTIONS §6) —
when a site's DOM changes, exactly one file changes.

## Troubleshooting

**`dev user not seeded`** — the API started before seed ran. Run `docker compose exec api python -m scripts.seed`.

**`fetcher 'nikkei' not implemented yet`** — expected. Only RSS works in phase 1.

**Celery worker won't pick up tasks** — make sure it's subscribed to the right queues: `--queues=default,fetch`. The compose file already does this.

**403s from Reuters/BBC on first run** — some feeds rate-limit aggressively by IP. Wait a minute and retry. Adjust `FETCH_USER_AGENT` to include a real contact URL (per CONVENTIONS §1).

## Tests

```bash
docker compose exec api pytest
```

Unit tests live in `tests/` and cover `app/core/utils.py` (URL canonicalization, hashing) and service-layer logic. Fetcher tests are deferred — per CONVENTIONS §13, record-and-replay fixtures against real pages, not mocks.

## Dev conventions

See `/CONVENTIONS.md` (frontend repo). The short version:

- Services hold business logic. Routes are thin.
- Tasks take IDs, not ORM objects. All tasks are idempotent.
- Fetcher failures raise the right `FetchError` subclass. Retry policy in `tasks.py` keys off the class.
- All writes in a transaction. All schema changes through Alembic.
- snake_case in DB, camelCase on the wire.
