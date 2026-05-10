"""AI providers + summarize service.

Each provider implements `complete(prompt, *, api_key, model)` and returns a
plain string. We only depend on httpx — no provider SDKs — so adding a new
provider is one new function.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ValidationError
from app.core.logging import get_logger
from app.models import Article, Source
from app.services import settings_service

log = get_logger("ai_service")


# ─── error ──────────────────────────────────────
class AIProviderError(AppError):
    status_code = 502
    code = "ai_provider_error"


# ─── prompt ─────────────────────────────────────
DEFAULT_PROMPT = """\
你是一名新闻编辑，正在撰写一份当日简报。

下面是过去 24 小时聚合的多语种新闻列表（含标题、摘要、来源、地区）。
请生成一份**全部使用中文**的简洁简报：

1. 按 **国家 / 地区** 分组（例如美国、日本、中国、英国、欧洲、国际等），
   每个分组使用 markdown 二级标题（`## 美国`）。
2. 每个分组下列 2–6 条新闻，每条给：
   - 一行中文标题（概括即可，无需照搬原文）
   - 1–2 句中文上下文（说明为什么值得关注）
3. 跳过娱乐八卦、明星私事、纯重复的转载。
4. 多个来源报道同一事件时合并为一条，并在末尾用括号注明 2 个来源名。
5. 最后用 `## 关注主线` 列出 3–5 个跨地区的主题或趋势。

要求：简洁；纯 markdown；不要写引言或寒暄；不要重复用户的指令。

新闻列表：
{articles}
"""


# ─── article fetching ───────────────────────────
@dataclass
class ArticleSnippet:
    title: str
    summary: str
    source: str
    lang: str
    region: str
    url: str
    published_at: datetime


async def collect_today_articles(
    db: AsyncSession, *, hours: int = 24, limit: int = 80
) -> list[ArticleSnippet]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        await db.execute(
            select(Article, Source)
            .join(Source, Source.id == Article.source_id)
            .where(Article.published_at >= cutoff)
            .where(Article.deleted_at.is_(None))
            .order_by(Article.published_at.desc())
            .limit(limit)
        )
    ).all()

    out: list[ArticleSnippet] = []
    for art, src in rows:
        out.append(
            ArticleSnippet(
                title=art.title,
                summary=(art.summary or "").strip(),
                source=src.name,
                lang=str(src.lang),
                region=src.region,
                url=art.url,
                published_at=art.published_at,
            )
        )
    return out


def render_articles_block(items: list[ArticleSnippet]) -> str:
    """Render the articles into a compact text block for the prompt."""
    parts: list[str] = []
    for i, it in enumerate(items, 1):
        ts = it.published_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        sumline = (it.summary[:280] + "…") if len(it.summary) > 280 else it.summary
        parts.append(
            f"[{i:03d}] {ts} · {it.source} ({it.region}/{it.lang})\n"
            f"     {it.title}\n"
            f"     {sumline}"
        )
    return "\n\n".join(parts)


# ─── provider plumbing ──────────────────────────
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "minimax": "MiniMax-Text-01",
}

# Full URL to POST to. Anthropic uses its own /v1/messages shape; the others
# all accept the OpenAI chat-completions shape under different paths.
DEFAULT_ENDPOINTS = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai":    "https://api.openai.com/v1/chat/completions",
    "deepseek":  "https://api.deepseek.com/chat/completions",
    "minimax":   "https://api.minimaxi.com/v1/text/chatcompletion_v2",
}

_HTTP_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


_COMMON_HEADERS = {
    "User-Agent": "observer-aggregator/0.1",
    "Accept": "application/json",
}


async def _call_anthropic(prompt: str, *, api_key: str, model: str, url: str) -> str:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            url,
            headers={
                **_COMMON_HEADERS,
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    if resp.status_code >= 400:
        raise AIProviderError(f"anthropic {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    blocks = data.get("content", [])
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


async def _call_openai_compat(
    prompt: str,
    *,
    api_key: str,
    model: str,
    url: str,
    label: str,
) -> str:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            url,
            headers={
                **_COMMON_HEADERS,
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 4096,
            },
        )
    if resp.status_code >= 400:
        raise AIProviderError(f"{label} {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    # OpenAI / DeepSeek / Minimax (chatcompletion_v2) all return the same shape
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise AIProviderError(
            f"{label} unexpected response shape: {e}; body[:300]={str(data)[:300]}"
        ) from e


async def _call_openai(prompt: str, *, api_key: str, model: str, url: str) -> str:
    return await _call_openai_compat(prompt, api_key=api_key, model=model, url=url, label="openai")


async def _call_deepseek(prompt: str, *, api_key: str, model: str, url: str) -> str:
    return await _call_openai_compat(prompt, api_key=api_key, model=model, url=url, label="deepseek")


async def _call_minimax(prompt: str, *, api_key: str, model: str, url: str) -> str:
    return await _call_openai_compat(prompt, api_key=api_key, model=model, url=url, label="minimax")


PROVIDER_FNS: dict[str, Callable[..., Awaitable[str]]] = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "deepseek": _call_deepseek,
    "minimax": _call_minimax,
}


# ─── main entry ─────────────────────────────────
@dataclass
class SummaryResult:
    summary: str
    provider: str
    model: str
    article_count: int
    used_custom_prompt: bool


async def summarize_today(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider: str | None,
    custom_prompt: str | None,
    model: str | None = None,
    hours: int = 24,
    article_limit: int = 80,
) -> SummaryResult:
    cfg = await settings_service.read_settings(db, user_id)
    chosen = (provider or cfg.default_provider).lower()
    if chosen not in settings_service.PROVIDERS:
        raise ValidationError(f"unknown provider {chosen!r}")
    if chosen not in PROVIDER_FNS:
        raise ValidationError(f"provider {chosen!r} not implemented")

    api_key = await settings_service.get_provider_key(db, user_id, chosen)
    if not api_key:
        raise ValidationError(
            f"no API key configured for {chosen}. add one in /settings."
        )

    articles = await collect_today_articles(db, hours=hours, limit=article_limit)
    if not articles:
        raise ValidationError("no articles in the last %d hours to summarize" % hours)

    used_custom = False
    if custom_prompt and custom_prompt.strip():
        prompt_template = custom_prompt
        used_custom = True
    elif cfg.custom_prompt and cfg.custom_prompt.strip():
        prompt_template = cfg.custom_prompt
        used_custom = True
    else:
        prompt_template = DEFAULT_PROMPT

    if "{articles}" not in prompt_template:
        prompt_template = prompt_template + "\n\nArticles:\n{articles}"

    prompt = prompt_template.replace("{articles}", render_articles_block(articles))

    model_override = await settings_service.get_provider_model(db, user_id, chosen)
    final_model = model or model_override or DEFAULT_MODELS[chosen]

    endpoint_override = await settings_service.get_provider_endpoint(db, user_id, chosen)
    final_url = endpoint_override or DEFAULT_ENDPOINTS[chosen]

    log.info(
        "ai.summarize.start",
        provider=chosen,
        model=final_model,
        url=final_url,
        n=len(articles),
    )
    try:
        text = await asyncio.wait_for(
            PROVIDER_FNS[chosen](
                prompt, api_key=api_key, model=final_model, url=final_url
            ),
            timeout=180,
        )
    except asyncio.TimeoutError as e:
        raise AIProviderError(f"{chosen} timed out after 180s") from e
    except httpx.HTTPError as e:
        raise AIProviderError(f"{chosen} network error: {e}") from e

    log.info("ai.summarize.done", provider=chosen, chars=len(text))
    return SummaryResult(
        summary=text,
        provider=chosen,
        model=final_model,
        article_count=len(articles),
        used_custom_prompt=used_custom,
    )
