# Observer — 代码规范与注意事项

这是给 Observer 新闻聚合项目写代码时的参考。分四个层次：**底线**（绝不能违反，多数涉及法律、安全、数据完整性）、**约定**（团队/AI 协作一致性）、**踩坑**（这个项目特有的、反复会出问题的地方）、**品味**（可讨论但默认如此）。

底线违反 = 立刻停工修复。约定违反 = PR 打回。踩坑未遵守 = code review 指出。品味 = 讨论但不强制。

---

## 目录

1. [项目定位与法律底线](#1-项目定位与法律底线)
2. [仓库结构与命名](#2-仓库结构与命名)
3. [前端规范（Next.js / TS / Tailwind）](#3-前端规范)
4. [后端规范（FastAPI / Python）](#4-后端规范)
5. [数据模型与数据库](#5-数据模型与数据库)
6. [抓取器（scrapers / fetchers）](#6-抓取器)
7. [安全与隐私](#7-安全与隐私)
8. [NER 与实体追踪](#8-ner-与实体追踪)
9. [搜索（Meilisearch）](#9-搜索)
10. [语义层（embeddings / pgvector）](#10-语义层)
11. [任务与调度（Celery / Redis）](#11-任务与调度)
12. [可观测性与运维](#12-可观测性与运维)
13. [测试](#13-测试)
14. [Git 与 PR](#14-git-与-pr)
15. [AI 协作说明](#15-ai-协作说明)

---

## 1. 项目定位与法律底线

### 底线

- **这个产品是给自己和极小的熟人圈用的"Pocket + 名人雷达"，不是对外公开的新闻平台。** 任何让它变成"公开可注册的付费墙内容再分发平台"的改动，都应该被拒绝。
- **永远不把完整付费墙文章向不特定多数人提供。** 即使是聚合二十家媒体的精彩段落做"每日摘要"邮件，也不行——这是编辑行为，版权风险最高。
- **Robots.txt 要读。** 不抓 `Disallow` 路径。不抓明确声明不允许机器爬取的站。
- **遵守 `User-Agent` 礼貌规则。** 真实 UA + 联系方式（email/domain），不伪装成 Googlebot 或大牌浏览器"欺骗"反爬。
- **抓取限速。** 每家站 1 分钟不超过 10 次请求起步，被警告就再降。宁可慢，不要被封。
- **个人登录 cookie 只能用于抓取"你作为该账号合法能访问的内容"。** 不用同一份 cookie 跑订阅数量超过合同允许的并发会话。不共享 cookie 给其他用户。

### 约定

- 产品文案里永远说 "personal reader" / "个人阅读器"，不说 "news platform" / "新闻平台"。公开口径影响法律定性。
- 文章存储**默认只存摘要 + 首段 + 原文链接**；全文抽取只在用户本人访问该条目时按需触发并缓存。（这是向"更安全"那端靠的默认，以后确实需要全量索引时再讨论。）
- 所有对外渲染的详情页在页脚都要有醒目的 "View original on {source}" 链接。

### 踩坑

- **付费墙 cookie 过期速度比你想象的快。** Nikkei/FT 大约 2–4 周，Bloomberg/WSJ 一两个月。要在 UI 和 push 里提前 72h 提醒重新导入。
- **图片防盗链。** 付费站的图片直连会 403。所有 `<img src>` 必须过自家代理 `/img?url=...`，代理带 `Referer` + 缓存到对象存储。前端绝不直引原站图片。
- **订阅合同的"单用户"条款。** Economist 个人订阅一般只允许 1–3 设备。高频脚本化访问会触发他们的风控，号被封。脚本访问要像人一样——慢、随机、带停顿、不 24 小时跑。

---

## 2. 仓库结构与命名

### 最终结构（目标，当前只有 `frontend/`）

```
observer/
├── frontend/              # 这个仓库当前的 news-aggregator/ 目录
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── package.json
├── backend/               # FastAPI
│   ├── app/
│   │   ├── api/           # 路由
│   │   ├── core/          # config, security, db
│   │   ├── models/        # SQLAlchemy
│   │   ├── schemas/       # pydantic
│   │   └── services/      # 业务逻辑（非 HTTP）
│   ├── tests/
│   └── pyproject.toml
├── workers/               # Celery workers
│   ├── fetchers/          # 每源一文件
│   │   ├── __init__.py
│   │   ├── base.py        # BaseFetcher 抽象类
│   │   ├── rss.py         # 通用 RSS fetcher
│   │   ├── nikkei.py
│   │   ├── caixin.py
│   │   └── ...
│   ├── ner.py
│   ├── embed.py
│   ├── notify.py
│   └── scheduler.py
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   └── migrations/        # alembic
└── docs/
    ├── CONVENTIONS.md     # 本文件
    └── runbook.md
```

### 约定

- 所有 **slug**（source、entity、tag）用 **kebab-case**（`south-china-morning-post`, `elon-musk`, `bank-of-japan`）。不缩写得看不出来——`scmp` 可以但因为它是通用缩写；`nyt` 不行（要用 `new-york-times`）。
- **数据库列名用 snake_case**，**TypeScript/前端用 camelCase**。Pydantic 的 schema 在序列化层用 `alias_generator=to_camel` + `populate_by_name=True` 做自动转换，不要在每个模型里手动起别名。
- **文件命名**：React 组件 `PascalCase.tsx`，非组件 TS 模块 `kebab-case.ts`，Python 模块 `snake_case.py`。
- **环境变量** `SCREAMING_SNAKE_CASE`，前缀分组：`DB_*`, `REDIS_*`, `FETCH_*`, `COOKIE_*`。

---

## 3. 前端规范

### 底线

- **永不在前端 `dangerouslySetInnerHTML` 未经清洗的 HTML。** 文章 `content_html` 必须在**后端** bleach 白名单清洗后入库，前端直接信任入库的版本。如果前端要再渲染用户内容（比如笔记），用 DOMPurify 再过一遍。
- **不把 API token / cookie 明文放进 localStorage 或 Cookie 以 `HttpOnly=false` 形式暴露给 JS。** session cookie 必须 `HttpOnly; Secure; SameSite=Lax`（登录跨域需要 `None` 时额外评估）。

### 约定

#### 服务端 vs 客户端组件

- **默认是服务端组件**。只有需要 `useState`、`useEffect`、浏览器 API、或引入只能客户端跑的库时，在文件顶部加 `'use client'`。
- `'use client'` 加在**最小粒度的叶子组件**，不要图省事整页都标记。列表页本身可以服务端渲染，筛选栏是 client 即可。
- 服务端组件里可以直接 `await fetch(...)`，**不要**用 TanStack Query；Query 只在 client 组件里用。
- 目前 `app/page.tsx` 是 client，因为筛选是 in-memory。**接上后端之后要改成 server 组件 + 把筛选下放给 `<FilterBar>` 内部的 client state 驱动 URL 参数**，feed 本身由服务端按 searchParams 渲染。

#### 数据获取

- **列表 / 详情页首屏用服务端渲染**，而不是客户端 fetch 后渲染——SEO 和首屏时间都重要。
- **互动性数据（订阅状态、保存的文章）用客户端 fetch + 乐观更新**。
- 用 `fetch(url, { next: { revalidate: 60 } })` 做 ISR，Feed 页 60s，详情页 300s，Sources/Subscriptions 页不缓存。
- 所有 API 调用走 `lib/api.ts` 的薄封装，不要散落在组件里 hardcode URL。

#### 样式

- **只用 Tailwind + `globals.css` 里的 `@layer components`**。不写 CSS Modules，不写 styled-components，不装 UI 组件库（shadcn/ui 除外，如果以后要引）。
- **语义色变量** 定义在 `globals.css` 的 `:root` / `.dark`，形如 `--bg`, `--ink`, `--line`, `--accent`。组件里永远用 `text-ink` 而不是 `text-[#1a1a1a]`。
- **响应式断点**：Tailwind 默认（`sm` 640 / `md` 768 / `lg` 1024 / `xl` 1280）。设计稿按移动优先写：默认样式就是手机样式，`md:` 及以上才是桌面。
- **字体层级仅用这几个**：`font-display`（Fraunces，标题）、`font-sans`（Plex，UI）、`font-serif`（Source Serif 4，正文）、`font-mono`（Plex Mono，代码/ID）。别的字体不加。
- **深色模式必须全程验证。** 任何新组件写完，手动 toggle 一次深色看是否崩溃。所有颜色必须经过 CSS 变量，不能硬编码 `text-white` 或 `bg-black`。
- **`.eyebrow` 小标签类已定义**——小型元信息（source / date / tag）一律用它，保证编辑美学的统一。

#### TypeScript

- `strict: true` 已开。**不允许 `any`**；实在需要用 `unknown` + 运行时检查。
- API 响应类型在 `lib/api-types.ts` 里定义，和后端 pydantic schema **一一对应**。如果对不上，后端改、前端改、文档改，三改其一。不能前后端偷偷用不同类型。
- 组件 props 用 `interface` 或 `type` 声明并导出——即使只在一个文件里用，也方便以后 lift up。
- **不用 `React.FC`**；直接 `function X(props: Props)` 或 `const X = ({ ... }: Props) =>`。

#### 状态管理

- 不引 Redux/Zustand/Jotai。**用 URL 参数 + React state + server 数据**就能覆盖到第 10 周。真到必须全局 store 的时候再讨论。
- 筛选条件、分页、排序**全部 URL 同步**，`useSearchParams` + `router.replace`。这样分享链接、刷新页面、浏览器前进后退都符合直觉。

### 踩坑

- **服务端组件里用 `new Date()` 会导致每次 SSR 都不同 → 客户端 hydrate 时报 mismatch。** `timeAgo` 这种"现在"相关的展示必须：(a) 在客户端 `useEffect` 里计算并覆盖，或 (b) 用相对时间戳（存 `publishedAtIso`，展示时 client-only 转换）。当前 mock-data 用的是 (a) 的精简版，数据上了以后要规范化。
- **`next/image` 对外部域名要白名单。** 付费站的 CDN 域名多变（Nikkei 光是图片就有 `article-image.nikkeipr.com` 和 `imgix-proxy.nikkei.com` 等），**不用 `next/image`**，用普通 `<img>` + 自家 `/img` 代理。
- **App Router 的 `params` 是 Promise（Next 15+）还是对象（Next 14）要看版本。** 当前依赖 Next 14，可以直接 `params.id`。升 15 时要改成 `await params`。
- **`'use client'` 文件不能用 async function as component**。需要异步的时候用 `useEffect` 或 React Query。
- **字体 CLS**：`next/font/google` 加载时用 `display: 'swap'`，并在 `globals.css` 给 `html` 设默认 `font-family`，避免 fallback 字体切换时版心跳动。
- **`line-clamp-*` 在 Firefox 老版本渲染不稳**——测试时要看 Firefox、Safari、Chrome 三个。
- **移动端 safe area** 一定要处理。`MobileNav` 已经加了 `pb-[env(safe-area-inset-bottom)]`；其它 fixed 定位元素在 iOS 上也要记得。

### 品味

- 卡片不加阴影。编辑风格用的是**细线条 + 留白 + 字体对比**，不是 Material elevation。
- 悬停态用颜色变化（`hover:text-accent`）或边框变化，不用 transform/scale。
- 按钮两种：**主按钮** = 实心 `bg-ink text-bg`；**次按钮** = `border border-line hover:border-line-strong`。不要第三种。
- icon 尺寸默认 `h-4 w-4`（16px），导航用 `h-[18px] w-[18px]`，超过 `h-5 w-5`（20px）的在 UI chrome 里几乎不出现。`strokeWidth={1.5}` 是默认，激活态可以升到 `2`。

---

## 4. 后端规范

### 底线

- **永不把密钥/cookie/敏感数据 log 出来。** 用结构化日志，敏感字段要显式 `redact`。任何 `print(cookies)` 进代码都是事故。
- **永不信任客户端传来的数据。** 所有 POST body 走 pydantic 校验；所有 path/query 参数也走 pydantic。
- **所有写操作必须在事务里。** `async with db.transaction()` 或 SQLAlchemy 的 `session.begin()`。多步骤写入之间断电崩溃不能留下半截数据。
- **永不用字符串拼 SQL。** ORM 或 `db.fetch("SELECT ... WHERE id = :id", {"id": id})` 参数化。

### 约定

#### 项目布局（FastAPI）

```
backend/app/
├── main.py              # FastAPI() 实例、中间件、路由挂载
├── api/
│   ├── feed.py          # /api/feed, /api/articles
│   ├── sources.py       # /api/sources, /api/sources/:slug/cookies
│   ├── entities.py      # /api/entities, /api/subscriptions
│   └── auth.py          # /api/auth/login, logout, me
├── core/
│   ├── config.py        # pydantic-settings 配置
│   ├── db.py            # engine, get_session
│   ├── security.py      # 密码 hash, JWT, Fernet
│   └── logging.py       # structlog 配置
├── models/              # SQLAlchemy，每个聚合根一文件
│   ├── article.py
│   ├── source.py
│   ├── entity.py
│   └── user.py
├── schemas/             # pydantic I/O 模型
│   ├── article.py
│   └── ...
└── services/            # 业务逻辑
    ├── feed_service.py
    ├── cookie_service.py
    └── subscription_service.py
```

#### 路由

- **路由函数只做 HTTP 层的事：** 参数解析、权限检查、调 service、序列化返回。业务逻辑一行都不写在路由里。
- **所有路由带 `response_model`。** 不写 `response_model` 的路由不许合并。
- HTTP 状态码按语义用：`200/201/204/400/401/403/404/409/422/429`。不要所有错误都 500。
- **分页强制 `limit` 上限**（我们定 100）。没有 `limit` 或 `limit > 100` 的请求 422。
- **幂等性**：所有 `POST /api/...` 如果是创建操作、且客户端可能重试的，接受 `Idempotency-Key` header，用 Redis 记 5 分钟去重。

#### pydantic schema

- **I/O 分开**：`ArticleCreate`（入参）、`ArticleRead`（出参）、`ArticleUpdate`（patch 用），不要共用一个 model。
- **Read schema 都配** `model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)`，一次性搞定 ORM 转换 + camelCase 输出。
- `datetime` 字段统一用 `aware datetime`（UTC）。从 DB 读出来的 naive datetime 在转 schema 时要 `.replace(tzinfo=timezone.utc)`。

#### SQLAlchemy

- 用 **SQLAlchemy 2.x** 语法，`Mapped[...]` + `mapped_column(...)`。不允许旧式 `Column` 写法。
- **async session** 贯穿始终（`AsyncSession`），不混用 sync。Celery worker 可以用 sync，那是独立进程。
- **`select(X).where(...)` 写法**，不写 `session.query(X)`。
- **一切关联查询显式 eager load**（`selectinload` / `joinedload`）；禁止触发 lazy load。Lazy load 在 async 里是定时炸弹。

#### 错误处理

- 定义统一异常层级：`AppError` → `NotFoundError`, `ValidationError`, `AuthError`, `RateLimitError`, `ExternalServiceError`。FastAPI 中间件统一捕获并转 HTTP。
- **永不 catch `Exception` 什么都不做**。Catch 具体异常，log，决定是重试还是抛。

### 踩坑

- **FastAPI 的 `BackgroundTasks` 不适合抓新闻。** 它在响应返回后阻塞 worker 进程直到任务完成，会拖累 API 吞吐。所有超过 100ms 的任务丢到 Celery。
- **SQLAlchemy async + PostgreSQL 要用 `asyncpg` 驱动**（`postgresql+asyncpg://...`）而不是 `psycopg2`。
- **`datetime.utcnow()` 是 naive datetime。** 用 `datetime.now(timezone.utc)`，后续所有时间比较才一致。
- **pydantic v1 和 v2 的 API 不同**。项目用 v2：`model_dump()` 不是 `dict()`，`ConfigDict` 不是 `class Config`。

### 品味

- 日志用 **structlog + JSON 输出**，本地开发用 rich renderer。不要 `print`。
- 配置用 **pydantic-settings** 从 env 加载，`.env.example` 列出所有变量（值留空或写占位）。

---

## 5. 数据模型与数据库

### 底线

- **一切写入走 Alembic migration**。手动 `ALTER TABLE` 改 prod 库 = 事故。
- **每次 schema 变更都必须 backward-compatible 至少一个版本**：先加列（可空）→ 双写 → 回填 → 改读 → 删列。不允许"删列 + 改代码"同一次部署。
- **`url` 字段永远要配一个 `url_hash CHAR(64) UNIQUE`**（sha256 hex），建 unique index 用它。URL 长度不定、有 `utm_*` 参数、有锚点，直接在 URL 上建 unique 会踩各种坑。

### 约定

- **所有表带 `created_at TIMESTAMPTZ DEFAULT NOW()` + `updated_at TIMESTAMPTZ`**。`updated_at` 在 app 层或 trigger 维护。
- **主键默认 BIGSERIAL / UUID v7**。短期 BIGSERIAL 够用；public-facing ID（要暴露给前端的）用 UUIDv7 避免按序号爬。当前前端 `a001/a002` 是 mock 占位，上线前要换。
- **软删除用 `deleted_at TIMESTAMPTZ NULL`**，不真删行。RSS/抓取历史哪天要回溯用得上。
- **索引命名** `idx_{table}_{col(s)}`，唯一索引 `uniq_{table}_{col(s)}`。Alembic 自动名称也差不多，就跟它。
- **JSONB 字段要在 migration 里写清楚结构文档**，否则半年后没人知道里面有什么。

### 踩坑

- **PostgreSQL 对 `UTC` 存储是 `TIMESTAMPTZ`，不是 `TIMESTAMP`。** 后者会在不同客户端时区下解释出不同值。全项目 `TIMESTAMPTZ`。
- **pgvector 的索引选择**：`hnsw` 对最新 Postgres 性能更好，`ivfflat` 需要先填数据再建索引才能 tune。项目用 hnsw。
- **Full-text 不在 Postgres 做。** 中日英混合分词 Postgres 的 `tsvector` 效果差得多。用 Meilisearch（见第 9 节）。
- **N+1 查询**：Feed 页拉 20 条文章后按 `source_id` 查 source ——必然 N+1。要么 join 要么 `selectinload(Article.source)`。
- **单表行数到千万级后**，索引大小会显著影响写入性能。`articles` 表早晚要按 `published_at` 月分区。先别做，到 500 万行再说。

---

## 6. 抓取器

### 底线

- **每个源一个文件**，放在 `workers/fetchers/{slug}.py`。源的变化只影响那一个文件。公共逻辑抽到 `base.py` / `rss.py`。
- **所有 fetcher 都继承 `BaseFetcher`** 并实现 `discover()` + `fetch_article(url)` 两个方法。`BaseFetcher` 统一处理限速、重试、错误分类、监控上报。
- **永远带 `Accept-Language` 和真实的 `User-Agent`。** UA 里写 `Observer/0.1 (+https://your-domain/bot)`，给站方一个联系方式。

### 约定

#### BaseFetcher 契约

```python
class BaseFetcher(ABC):
    slug: str                                # "nikkei"
    lang: Lang
    rate_limit_per_min: int = 6              # 默认 6/min
    needs_cookies: bool = False

    @abstractmethod
    async def discover(self) -> list[str]:
        """返回本次周期要抓的 URL 列表。失败抛 ExternalServiceError。"""

    @abstractmethod
    async def fetch_article(self, url: str, cookies: list[dict] | None) -> ArticleDoc:
        """抓单篇并抽取。失败抛 FetchError 子类之一（见下）。"""
```

#### 错误分类（强制）

```python
class FetchError(Exception): pass
class TransientError(FetchError): pass         # 重试
class AuthError(FetchError): pass              # cookie 失效 → 标记过期 + 通知用户
class NotFoundError(FetchError): pass          # 404，跳过不重试
class BlockedError(FetchError): pass           # 403/429，降速 + 告警
class ExtractionError(FetchError): pass        # 页面抓到了但解析失败 → 记录原 HTML 到 S3 供调试
```

这个分类 **每个 fetcher 都必须正确区分**。把 `AuthError` 当 `TransientError` 重试会导致 cookie 被更快风控。

#### 限速

- 用 `aiolimiter.AsyncLimiter` 或 Celery 的 `rate_limit`。每个源独立队列 + 独立限速，**一个源被封不影响其它源**。
- 被 429 时立即 sleep `Retry-After` header，再按 2^n 指数退避。连续 3 次 429 把源降级到"每小时 1 次"并 push 通知自己。

#### 正文抽取

- **RSS 源**：`feedparser` 读 feed，然后用 `trafilatura` 抽正文。不要信任 RSS 里的 `<description>`（很多站给节选）。
- **HTML 源**：优先 Playwright（稳），能走 httpx + lxml 的 2-3 年不改版的源用 httpx（快 10 倍）。
- **所有抽取结果过一层清洗**：白名单标签（`p h1-h4 ul ol li blockquote img figure figcaption em strong a code pre`），白名单属性（`href src alt`），JavaScript / event handler / style 一律剥离。这层在 `workers/extract.py` 统一做，不让每个 fetcher 自己实现。

#### 去重

- 抓下来先算 `url_hash = sha256(canonicalize(url))`——`canonicalize` 去掉 `utm_*`、片段、尾斜杠。库存在则跳过。
- 入库后异步算 `content_hash = sha256(normalized_text)`；同一周内 `content_hash` 相同的视为同事件，后来者挂到前者作为"additional sources"，不独立展示。（这一层要等 Week 10 语义去重上线后再开，MVP 先不做。）

### 踩坑

- **Playwright 内存泄漏**。长跑 worker 一周能吃掉 4GB。**每 100 篇文章重启一次 browser context**（不是整个 browser，是 context）。
- **Cloudflare Challenge**（SCMP/Caixin 时不时遇到）：`playwright-stealth` 能绕过 80%。剩下 20% 用浏览器指纹修正 + 人工间歇访问，不要死磕。
- **网页 lazy-load 图片**：`src` 常常是占位 svg，真图在 `data-src` / `data-original` / `srcset`。抽取时要检查这些属性。
- **字符编码**：日文站常年 Shift-JIS 和 UTF-8 混用，中文站繁简体切换。统一在 httpx 层用 `response.text`（它会看 `Content-Type` 和 meta charset），实在不行用 `chardet`。
- **相对 URL**：文章里的图片和链接经常是 `/images/foo.jpg` 这种相对路径。入库前 **`urljoin(article_url, src)` 转绝对**。否则前端渲染时全是死链。
- **时区**：`published_at` 抽出来经常只有日期，或带 JST/CST 字样。用 `dateutil.parser` + 源的默认时区 fallback，最终存 UTC。
- **重复 fetch_article 任务**：队列 ack 之前进程挂了会重投递。fetcher 必须幂等——`INSERT ... ON CONFLICT (url_hash) DO NOTHING`。

### 品味

- fetcher 写完先跑 10 次不同文章做 smoke test，目测抽取结果。过早做单测意义不大——网页会变，mock fixture 过几周就失效。
- 每个 fetcher 带一个 `README.md`（在同目录）写明：这个源的特殊性、需要什么 cookie、已知不抓哪些栏目、历史坑点。半年后回来维护的那个人（可能就是你自己）会谢你。

---

## 7. 安全与隐私

### 底线

- **Cookie 静态加密**。Fernet（AES-128-CBC + HMAC）或 AES-256-GCM。密钥从 env 读，**绝不进代码或 Git**。密钥轮换要有流程（旧密钥保留解密能力至少 30 天）。
- **密钥不以明文形式进日志**。就算是 debug 日志。
- **密码存 argon2id**（passlib[argon2]），不用 bcrypt 了（bcrypt 72 字节截断的坑见过多次）。
- **Session 用 HttpOnly + Secure + SameSite=Lax 的 cookie**；不放 localStorage。
- **CSRF 防御**：状态修改接口用 `SameSite=Lax` 足够覆盖大多数场景；跨站 POST 场景用 double-submit token。
- **SQL 注入**：已经在第 4 节说了。强调两次。
- **XSS**：已在第 3 节说了。强调两次。
- **速率限制**所有公开端点（即使"只有自己用"，也会被扫）。登录用 5 次/min/IP，其它 60 次/min/IP 起步。

### 约定

- 敏感操作（cookie 导入、改密、删账号）二次确认。
- 管理后台/调试端点与公开端点**不同子域 + 不同 session**。本地开发可以走同一个 FastAPI，生产必须分离。
- 错误信息不泄漏内部细节。`except Exception: log(); return 500 "internal"`。traceback 只进日志。
- 文件上传（如果将来加）走 MIME 检测（magic bytes），不只看扩展名。

### 踩坑

- **Fernet 密钥是 base64-encoded 32 字节**。直接把随机 32 字节当密钥会报错。用 `Fernet.generate_key()` 生成。
- **环境变量 `.env` 文件**本地开发可以有，**绝不进 Git**（`.gitignore` 已包含）。生产靠 secret manager 或 systemd EnvironmentFile。
- **Playwright 跑在容器里默认用 root**，下载到 `/root/.cache`。要 `USER node` + 预装好浏览器，否则每次 cold start 都下载。
- **CORS**：FastAPI 的 `CORSMiddleware` 生产只白名单自家 frontend domain，不开 `*`。

---

## 8. NER 与实体追踪

### 底线

- **别名表是真理之源，NER 输出是候选。** 匹配算法是"实体识别得到文本 → 在别名表里查 → 命中才算"，不是"NER 识别出来就当新实体入库"。否则别名爆炸。
- **实体的 canonical 身份靠 Wikidata QID 锚定**。一个 QID 对应一行 entity。没有 QID 的 entity 不入库。冷启动 50 个人物/公司从 Wikidata 拉。

### 约定

- 三套 spaCy pipeline 按 article.lang 路由：`zh_core_web_trf` / `ja_core_news_lg` / `en_core_web_trf`。未识别语言默认走 en。
- NER 只取 `PERSON` 和 `ORG` 两类。`GPE`（地理）和 `EVENT` 等以后再说。
- 别名模糊匹配用 **RapidFuzz** + 阈值 90。阈值以下归为"疑似"，不写 `article_entities` 表，只写 `ner_candidates` 表供以后人工 review。
- **每家新闻的标题和正文都要过 NER**——只看标题会漏掉"X 表示......"这种主语在正文的情况。
- 内存里保留一份全实体别名的 **Aho-Corasick 自动机**，而不是每篇文章对每个 entity 做 N^2 fuzz。Aho-Corasick 对 10 万别名的匹配是 O(text length)。

### 踩坑

- **中文 NER 对"马斯克"、"特朗普"这种音译识别率不稳定**。用 `zh_core_web_trf` 比 `_lg` 好一截，但还会漏。冷启动时要人工补一些典型错例。
- **日文全角 / 半角**：`イーロン・マスク` 和 `ｲｰﾛﾝ･ﾏｽｸ` 都可能出现。入库前 NFKC normalize。
- **同名不同人**：`John Smith` 很多。Wikidata QID 唯一化能解决，但如果 NER 识别到 "John Smith" 而别名表有 3 个 John Smith 的 QID——当前策略是**不匹配，写入 `ner_candidates` 供后续消歧**。别瞎猜。
- **spaCy transformer 模型吃显存**。没 GPU 的话 CPU 上 `_trf` 要 500ms / 篇，批量处理必须排队 + 限并发。
- **标题用 NER 很不稳定**（上下文太短）。标题里出现的别名优先用字符串匹配（Aho-Corasick），正文才走 NER + 别名双验证。

---

## 9. 搜索

### 底线

- **Meilisearch 只索引摘要 + 标题 + 元数据，不索引全文付费墙内容给未登录用户。** 搜索结果要按用户的可访问范围过滤（Meili 的 `filter` 参数）。

### 约定

- 主索引 `articles`，文档结构：
  ```json
  {
    "id": "...",
    "title": "...",
    "summary": "...",
    "source_slug": "...",
    "source_name": "...",
    "lang": "ja",
    "region": "JP",
    "tier": "paywall",
    "published_at_ts": 1710000000,
    "entity_slugs": ["elon-musk", "tesla"]
  }
  ```
- 可搜索字段：`title, summary`。
- 可过滤字段：`source_slug, lang, region, tier, entity_slugs, published_at_ts`。
- 可排序字段：`published_at_ts`。
- **同步策略**：文章入库后投递一个 Celery 任务 `index_article(id)`；Meili 挂了任务进重试队列，不阻塞入库。每晚一次 full reindex 兜底。

### 踩坑

- Meili 的日语分词 0.30+ 版本已内置（基于 Lindera），但中文分词还不够好——必要时预处理时自己 jieba 分词后存 `title_tokens` 再索引。
- **排序字段必须声明在 `sortableAttributes`**，默认不可排序。
- Meili 的 `filter` 表达式语法和 SQL 不一样（用 `AND/OR`，不是 `&&/||`）。

---

## 10. 语义层

### 底线

- embedding 模型选定后**至少锁 6 个月**。换模型 = 全库重算向量。轻易不换。

### 约定

- 当前选 `paraphrase-multilingual-MiniLM-L12-v2`，384 维，覆盖 zh/ja/en。
- 每篇文章存**一个**向量（title + summary + 首两段拼接后 embed）。不做段落级向量，简单有效。
- 相似度阈值：**cosine > 0.88** 视为"同一事件的不同报道"。低于就是相关话题。

### 踩坑

- **pgvector 的 HNSW index 建索引要先有数据**。冷启动时先灌 1 万条再建索引，直接在空表上建索引后批量插入会很慢。
- 向量列的存储开销：384 * 4 bytes = 1.5KB/行。10 万篇文章 150MB，还行；100 万篇 1.5GB，要考虑拆到单独表或按时间分区。
- **embedding 是 CPU-heavy**。跑在 API 请求里绝对不行，只能在 worker 里批处理，每批 32 篇。

---

## 11. 任务与调度

### 约定

- Celery broker = Redis，result backend 关掉（我们不需要 `.get()` 结果）。
- **一个任务只做一件事**。抓 → 存 → 抽实体 → 向量化 → 通知 = 5 个 task，链式触发（`fetch_article.apply_async(..., link=extract_entities.s())`），不是一个大任务。
- **所有任务幂等**。任何任务被重复执行两次都必须产生相同效果。
- **任务参数只传 ID，不传对象**。`extract_entities(article_id=123)`，不是 `extract_entities(article=<Article ...>)`。对象序列化跨进程不可靠。
- **任务重试策略**：`max_retries=3`, `default_retry_delay=60 * (2 ** current_retry)`（指数退避）。`AuthError` / `NotFoundError` 子类设 `max_retries=0`。
- **调度用 Celery Beat + DB-backed schedule**（django-celery-beat 或 celerybeatmongo 的同类库），不要 hardcode 在代码里——加源时不用发版。

### 踩坑

- **Celery 的 fork vs spawn**。Playwright 在 fork worker 里跑会挂（asyncio event loop 被 fork 继承）。用 `--pool=prefork` + Playwright 的 sync API，或 `--pool=solo` + async。我们选后者。
- **任务积压监控**：每个队列的 pending 数有告警阈值，超过就降级抓取频率。
- **DB 连接池**：Celery worker 的 SQLAlchemy engine 要在 `worker_process_init` 信号里重建，主进程的 engine 不能跨 fork 用。

---

## 12. 可观测性与运维

### 约定

- **结构化日志（JSON）+ request id**。每条日志带 `request_id`, `user_id`（如有）, `source_slug`（如相关）, `article_id`（如相关）。
- **健康检查三级**：
  - `/livez` — 进程活着（永远返回 200）
  - `/readyz` — DB + Redis 可连（依赖检查）
  - `/healthz` — 综合（加上 fetcher 心跳、Meili 可达）
- **关键指标**（Prometheus）：`fetch_success_total{source}`, `fetch_failure_total{source, error_class}`, `fetch_duration_seconds`, `article_ingested_total`, `ner_processed_total`, `cookie_status{source, status}`。
- **alert** 三条就够：
  1. 任一 source 连续 3 小时 0 入库（可能挂了）
  2. 任一 source cookie 状态 expired 或 expiring（3 天内）
  3. Celery 队列积压 > 1000

### 踩坑

- Playwright 崩溃后的 zombie chromium 进程会积累，`docker stats` 里容器内存持续涨——加 cron 每小时 `pkill -f chromium-runner` 兜底。
- PostgreSQL 的 autovacuum 在 `articles` 这种高写入表上要调 `autovacuum_vacuum_scale_factor=0.02`，否则 bloat 严重。
- Redis 的 maxmemory 和 eviction policy：broker 用的 Redis 不能 LRU eviction（会丢消息），要 `noeviction` + 监控。缓存用的 Redis 另开一个 instance 才能 LRU。

---

## 13. 测试

### 约定

- **单元测试覆盖纯函数**：URL canonicalize、别名归一化、时间解析、权限判断。这些逻辑稳定、bug 影响大、测试快。
- **集成测试覆盖 API 路由**：用 `pytest-asyncio` + `httpx.AsyncClient` + 测试数据库（每次 teardown）。每个路由至少 3 个 case：happy path、无权限、参数错误。
- **不对 fetcher 写 unit test**。网页变更频繁，mock fixture 过几周就失效。fetcher 用**录制-回放**：每家源录 3 个真实页面到 `tests/fixtures/{slug}/*.html`，测试只断言抽取结果的 shape（有 title、有 >200 字正文、有 published_at），不断言具体字符串。网页结构变了测试会自然挂掉提醒你。
- 前端用 **Playwright** 写 3-5 个端到端流程：看 feed → 点进文章 → 改订阅 → 导入 cookie → 搜索。不写组件级单测。

### 踩坑

- **测试数据库要真 Postgres，不用 SQLite**。pgvector、TIMESTAMPTZ、JSONB 这些 SQLite 都没有。用 `testcontainers-python` 起一次性 Postgres。
- 测试里的 `datetime.now()` 要 freeze 或注入——`freezegun` 或 dependency injection。

---

## 14. Git 与 PR

### 约定

- **分支命名**：`feat/xxx`, `fix/xxx`, `chore/xxx`, `refactor/xxx`, `docs/xxx`。
- **Commit message** 走 Conventional Commits：`feat(fetcher): add Nikkei support`。
- **PR 标题 = 最终 squash commit message**。PR 描述写明：动机、改动摘要、测试方式、截图（前端改动）、roll-back 方案（数据库改动）。
- **一个 PR 一件事**。混了前后端 + DB migration + 重构 4 类改动的 PR 直接打回拆分。
- **所有 PR 要过 CI**：lint + type check + test。CI 绿才能合。
- **DB migration 的 PR 单独提**，不和业务代码混。

### 踩坑

- **Alembic 的 autogenerate 不是自动正确的**。它生成后人要读一遍——尤其涉及 rename（它会识别成 drop + add，丢数据）、index 名冲突、enum 新增值（Postgres 里 enum 加值要特殊语法）。
- **合并 migration**：两个人分头写了 migration，merge 时出现两个 head revision。用 `alembic merge heads` 生成合并 revision，不要手改文件。

---

## 15. AI 协作说明

项目里多数代码会和 AI 助手（Claude / Cursor / Copilot）协作完成。几条特别注意：

- **AI 生成代码也要走上面所有规范**。不要因为"这是 AI 写的"就放行未类型化、裸 `except`、硬编码密钥的代码。
- **给 AI 的上下文要包含本文件的链接**。大段改动前让它读 CONVENTIONS.md。
- **AI 倾向于生成 "看起来合理但不必要" 的依赖**（什么 zustand、redux-toolkit、react-hook-form）。审 PR 时看 `package.json` / `pyproject.toml` 的 diff，没理由引入的新包 → 砍。
- **AI 倾向于写过度工程化的抽象**。三个 fetcher 的时候不需要 plugin 注册机制 + IoC 容器。二十个再说。YAGNI。
- **AI 不知道当前项目状态**。它可能给你写一个 "接上 Redis 的完美缓存层"，但你现在根本没跑 Redis。让它先读 `docker-compose.yml` 再动手。
- **AI 生成的 SQL migration 必须人工 review**。autogen 出来的 drop column 如果没人看，上生产就是事故。
- **AI 不会识别法律风险**。它会很乐意帮你写"把 Bloomberg 的文章全文缓存下来以供 100 个用户访问"的代码。你要把关。
- **秘密绝不贴给 AI**。真实 cookie、API key、生产 DB URL，都不能出现在和 AI 的对话里。临时值脱敏或用假值。

---

## 附录：快速决策树

遇到一个写代码的场景拿不准时：

1. **会不会让项目变成"公开再分发付费墙内容"？** → 是 → 停，换方案。
2. **会不会把敏感数据（cookie/密码/密钥）暴露出去？** → 是 → 停。
3. **这个地方之前踩过坑吗？** → 翻"踩坑"章节。
4. **前/后端接口的类型对得上吗？** → 对不上 → 修至少一端的类型声明后再写代码。
5. **跑失败会发生什么？** → 想好错误分类（第 6 节的 `FetchError` 子类，第 4 节的 `AppError`）再写。
6. **下一个人（或三个月后的自己）能看懂吗？** → 看不懂 → 加注释或抽函数。注释写"为什么"，不写"做什么"。

---

*本文件是活文档。遇到新坑就加进来。约定改了要 PR。*
