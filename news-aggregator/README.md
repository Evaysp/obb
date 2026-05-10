# Observer — news aggregator (frontend shell)

A personal news reader that pulls from RSS + paywalled sites, renders everything
in one place (no redirects), and tracks mentions of people and companies you
follow.

This repo is **the frontend shell** with mock data. Every page renders, every
component is styled, and the wiring is in place for backend endpoints to drop
in.

## What's in here

```
app/
├── layout.tsx                      root: fonts, theme, responsive shell
├── page.tsx                        feed home (hero + grid + filters)
├── a/[id]/page.tsx                 article detail (editorial prose)
├── sources/page.tsx                source management grid
├── sources/[slug]/cookies/page.tsx cookie JSON import form
├── subscriptions/page.tsx          entity tracking + subscribe toggle
└── search/page.tsx                 unified search (articles, entities, sources)

components/
├── Header.tsx                      sticky top bar + search + theme toggle
├── Sidebar.tsx                     desktop nav + followed entities
├── MobileNav.tsx                   bottom tab bar, <md only
├── ArticleCard.tsx                 default / hero / compact variants
├── FilterBar.tsx                   lang / region / tier dropdowns
└── ThemeProvider.tsx               next-themes wrapper

lib/
├── types.ts                        Source, Article, Entity, Lang
├── mock-data.ts                    11 sources, 20 articles, 12 entities
└── utils.ts                        cn, timeAgo, formatDate, hashHue
```

## Run

```bash
cd news-aggregator
npm install
npm run dev
# → http://localhost:3000
```

Fonts (Fraunces, IBM Plex Sans, Source Serif 4, IBM Plex Mono) load from
Google Fonts on first build — internet access required at build time. After
that they're bundled.

## Design language

- **Fraunces** for titles — editorial variable serif
- **IBM Plex Sans** for UI chrome
- **Source Serif 4** for body copy
- **IBM Plex Mono** for cookie payloads, IDs, kbd
- Warm-paper light mode (not pure white), warm-charcoal dark (not pure black)
- Subtle SVG paper-grain overlay
- Single ochre accent for links, unread indicators, paywall badges
- Sentence-case headings, small-caps eyebrows (`.eyebrow`)
- Hero placeholder imagery is CSS-generated from a hash of the article ID —
  no external image dependencies

## Hooking up the backend

Every page currently imports from `lib/mock-data.ts`. To go live, replace these
calls with `fetch` to your FastAPI routes:

| Mock call                        | Backend route                                      |
| -------------------------------- | -------------------------------------------------- |
| `articles`                       | `GET /api/feed?lang=&region=&tier=&cursor=`        |
| `getArticle(id)`                 | `GET /api/articles/:id`                            |
| `sources`                        | `GET /api/sources`                                 |
| `getSource(slug)`                | `GET /api/sources/:slug`                           |
| `entities`                       | `GET /api/entities?subscribed=true`                |
| `getArticlesByEntity(slug)`      | `GET /api/entities/:slug/articles`                 |
| Cookie form `handleSave`         | `POST /api/sources/:slug/cookies` (encrypts, saves)|
| Subscribe toggle                 | `POST /api/subscriptions` / `DELETE /api/subscriptions/:id` |

The feed page is already a `'use client'` component using `useMemo` for
filtering — swap the in-memory array for React Query / SWR with the same
filter state shape.

## Phase roadmap (from the original plan)

- **Week 1–3 · MVP.** This shell + RSS-only scraping for Asahi, NHK, BBC,
  Reuters, Caixin public feeds. Python worker with `feedparser` +
  `trafilatura`, PostgreSQL, nightly.
- **Week 4–6 · Paywall fetchers.** Playwright + encrypted cookie vault. Wire
  the cookie form on this shell to `POST /api/sources/:slug/cookies`. One
  fetcher module per source (`workers/fetchers/nikkei.py`, etc.) — hot-pluggable.
- **Week 7–9 · Search + tracking.** Meilisearch sidecar indexing articles.
  Wikidata bootstrap for the 50 most-tracked entities. spaCy NER pipelines
  (`zh_core_web_trf`, `ja_core_news_lg`, `en_core_web_trf`). Web Push + email
  notifier worker.
- **Week 10+ · Semantic layer.** pgvector + `paraphrase-multilingual-MiniLM`
  embeddings for cross-source dedup and personalized ranking.

## Known caveats in the shell

- Mock timestamps are computed relative to module-load time, so server render
  and client hydration timestamps can differ by ~1 second — not a problem in
  practice but will be gone once the backend serves stable ISO strings.
- The "Save cookies" button is a demo that validates JSON structure but does
  not actually POST anywhere yet.
- Subscribe toggles live in React state only; refresh the page and they
  revert to mock defaults.
- No authentication layer (middleware) — add when backend lands.

## Stack

Next.js 14 (App Router) · React 18 · TypeScript · Tailwind · next-themes ·
lucide-react. Zero other runtime deps.
