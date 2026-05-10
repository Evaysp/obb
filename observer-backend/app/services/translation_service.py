"""Translation service — caches per (article_id, target_lang) for 24h.

Cache layer: Redis (key `translation:{lang}:{id}`, JSON value, TTL 86400).
Miss layer: bulk-call the user's configured AI provider with a JSON-array
prompt designed for news translation (proper nouns + diplomatic-context aware).

Articles whose source language already matches the target are not sent to
the LLM — we cache the original strings as the "translation" so subsequent
calls are instant and we never burn tokens on no-op translations.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ValidationError
from app.core.logging import get_logger
from app.models import Article
from app.services import ai_service, settings_service

log = get_logger("translation_service")

CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h
MAX_BATCH = 8                     # small batches → fewer empty responses from
                                  # providers with tight output-token caps
FULL_BODY_CHAR_LIMIT = 8000       # cap content_html length sent to LLM
BLOCKS_PER_CALL = 6               # block-level: small batches keep prompts short


# ─── prompt ──────────────────────────────────────
TRANSLATION_PROMPT = """\
你是一名专业新闻翻译，擅长跨语种政治、经济、商业新闻的中文译写。

**任务**：把下面 N 篇外语新闻的"标题"和"摘要"翻译成简体中文。

**要求**：
1. **专有名词**（人名、机构名、地名、公司名、技术术语）按主流中文媒体的规范译法。
   例：Donald Trump → 唐纳德·特朗普（首次出现），后续可简称"特朗普"；
   Nikkei → 《日经》；Federal Reserve → 美联储；Reuters → 路透社；
   Asahi Shimbun → 《朝日新闻》；NHK → 日本放送协会(NHK)。
2. **国际关系与外交语境**：保持中立客观，不要带立场色彩，不要添加原文没有的判断或修饰。
   日中、中美、台海等敏感议题严格忠于原意，不引申、不暗示。
3. **头衔与机构缩写**首次出现时给出中文全称 + 原缩写：
   FT → 英国《金融时报》(FT)；ECB → 欧洲央行；BOJ → 日本央行(BOJ)。
4. **数字与单位**保留原值，按中文规范书写：
   100M USD → 1 亿美元；3 trillion yen → 3 万亿日元；2.5% → 2.5%。
5. **标题**保持新闻标题简洁感（10-25 字），不加"关于…的报道"等冗词。
6. **摘要**可更自然，1-3 句话。
7. **已是中文**或主体为中文的标题/摘要，原样返回不改。
8. 译文不要引号包裹，不要加引言或注释。

**输出**：严格的 JSON 数组，**绝对不要** markdown 代码块包裹，直接以 `[` 开头：

[{"id":123,"title":"译后标题","summary":"译后摘要"},{"id":124,"title":"...","summary":"..."}]

**输入文章**：
{articles_json}
"""


# ─── prompt for full-article (title + summary + content_html) ──────
FULL_TRANSLATION_PROMPT = """\
你是一名专业新闻翻译。请把下面这篇外语新闻翻译成简体中文。

**译法规则**：
- 专有名词按主流中文媒体规范：Trump → 特朗普；Federal Reserve → 美联储；
  FT → 英国《金融时报》(FT)；Nikkei → 《日经》。
- 国际关系敏感议题严格中立客观，不引申、不暗示。
- 数字单位规范：100M USD → 1 亿美元；3% → 3%。
- 头衔机构缩写首次给中文 + 原缩写。

**HTML 处理**：
- 严格保留所有 HTML 标签 (<p>, <h2>, <h3>, <a>, <img>, <blockquote>,
  <ul>, <li>, <strong>, <em>, <figure>, <figcaption> 等)，**只翻译标签之间的文字**。
- <a href="..."> 的 href 保持不变，只翻译链接显示文本。
- <img src="..."> 的 src 保持不变，alt 文字可以翻译。
- 不要新增 / 删除标签结构。

**输出格式**：严格按下面格式输出，标记一字不差，**不要** markdown 代码块，**不要** 写其他任何文字。

###TITLE###
中文标题
###SUMMARY###
中文摘要
###BODY###
中文正文 HTML
###END###

**待翻译**：

[TITLE]: {title}
[SUMMARY]: {summary}
[BODY HTML]:
{content_html}
"""


def _parse_delimited_translation(text: str) -> dict | None:
    """Parse the ###TITLE###/###SUMMARY###/###BODY###/###END### output.
    Returns None if any required section is missing or out of order."""
    if not text or not text.strip():
        return None
    markers = ["###TITLE###", "###SUMMARY###", "###BODY###", "###END###"]
    indices: list[int] = []
    for m in markers:
        i = text.find(m)
        if i < 0:
            return None
        indices.append(i)
    if not (indices[0] < indices[1] < indices[2] < indices[3]):
        return None
    title = text[indices[0] + len(markers[0]) : indices[1]].strip()
    summary = text[indices[1] + len(markers[1]) : indices[2]].strip()
    body = text[indices[2] + len(markers[2]) : indices[3]].strip()
    if not title or not body:
        return None
    return {"title": title, "summary": summary, "contentHtml": body}


# ─── error ───────────────────────────────────────
class TranslationError(AppError):
    status_code = 502
    code = "translation_error"


# ─── public API ──────────────────────────────────
async def translate_articles(
    redis: Redis,
    db: AsyncSession,
    *,
    user_id: UUID,
    article_ids: list[int],
    target_lang: str = "zh",
) -> dict[int, dict]:
    """Returns { article_id: { title, summary, cached: bool } } for all
    requested ids that exist in the DB. Cache hits and misses both included.
    """
    if target_lang != "zh":
        raise ValidationError(f"target_lang {target_lang!r} not supported (only 'zh' currently)")

    article_ids = sorted(set(int(i) for i in article_ids if isinstance(i, int) and i > 0))
    if not article_ids:
        return {}

    # ── 1. Cache lookup ──
    keys = [_cache_key(target_lang, aid) for aid in article_ids]
    raw_values: list[str | None] = []
    try:
        raw_values = await redis.mget(keys)
    except Exception as e:
        log.warning("translate.redis_mget_fail", err=str(e))
        raw_values = [None] * len(keys)

    out: dict[int, dict] = {}
    misses: list[int] = []
    for aid, raw in zip(article_ids, raw_values):
        if raw:
            try:
                obj = json.loads(raw)
                out[aid] = {
                    "title": obj.get("title", ""),
                    "summary": obj.get("summary", ""),
                    "cached": True,
                }
            except (json.JSONDecodeError, TypeError):
                misses.append(aid)
        else:
            misses.append(aid)

    if not misses:
        log.info("translate.all_cached", count=len(out))
        return out

    # ── 2. Fetch article rows ──
    rows = (
        await db.execute(select(Article).where(Article.id.in_(misses)))
    ).scalars().all()
    if not rows:
        return out

    # ── 3. Same-language no-op: cache original as "translation" ──
    by_id = {r.id: r for r in rows}
    needs_llm: list[Article] = []
    for aid in misses:
        a = by_id.get(aid)
        if a is None:
            continue
        if str(a.lang) == target_lang:
            # Original IS the target — store as-is so next call is instant
            out[aid] = {
                "title": a.title,
                "summary": a.summary or "",
                "cached": False,
            }
            await _store(redis, target_lang, aid, a.title, a.summary or "")
        else:
            needs_llm.append(a)

    if not needs_llm:
        return out

    # ── 4. Pick a provider that's actually configured ──
    cfg = await settings_service.read_settings(db, user_id)
    # Prefer the user's default; fall back to whichever has a key.
    candidates = [cfg.default_provider, *cfg.configured_providers]
    provider: str | None = None
    api_key: str | None = None
    for cand in candidates:
        if cand not in ai_service.PROVIDER_FNS:
            continue
        k = await settings_service.get_provider_key(db, user_id, cand)
        if k:
            provider = cand
            api_key = k
            break
    if provider is None or api_key is None:
        raise ValidationError(
            "no AI provider key configured; add one in /settings before translating"
        )

    model_override = await settings_service.get_provider_model(db, user_id, provider)
    model = model_override or ai_service.DEFAULT_MODELS[provider]
    endpoint_override = await settings_service.get_provider_endpoint(db, user_id, provider)
    url = endpoint_override or ai_service.DEFAULT_ENDPOINTS[provider]

    # Run batches in parallel
    batches = [needs_llm[i : i + MAX_BATCH] for i in range(0, len(needs_llm), MAX_BATCH)]
    log.info(
        "translate.llm.start",
        provider=provider,
        model=model,
        misses=len(needs_llm),
        batches=len(batches),
    )

    results = await asyncio.gather(
        *[
            _translate_one_batch(
                articles=b,
                provider=provider,
                api_key=api_key,
                model=model,
                url=url,
                target_lang=target_lang,
            )
            for b in batches
        ],
        return_exceptions=True,
    )

    # Collect every successfully translated id across batches
    translated_ids: set[int] = set()
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            log.warning("translate.batch_fail", err=str(r), batch=i)
            continue
        for aid, tr in r.items():
            out[aid] = {**tr, "cached": False}
            translated_ids.add(aid)
            # Only cache real translations, never fallback originals
            await _store(redis, target_lang, aid, tr["title"], tr["summary"])

    # Fall back to originals for ids the LLM didn't translate. Don't cache —
    # the user (or the next request) might succeed where this one didn't.
    batched_by_id = {a.id: a for batch in batches for a in batch}
    for aid, art in batched_by_id.items():
        if aid in translated_ids or aid in out:
            continue
        out[aid] = {
            "title": art.title,
            "summary": art.summary or "",
            "cached": False,
            "error": "translation skipped (provider returned empty / unparseable / echo)",
        }

    return out


# ─── full-article translation ───────────────────
async def translate_one_full(
    redis: Redis,
    db: AsyncSession,
    *,
    user_id: UUID,
    article_id: int,
    target_lang: str = "zh",
) -> dict:
    """Translate title + summary + content_html for one article. Cached in
    Redis under `translation:{lang}:{id}:full` with the same 24h TTL.
    """
    if target_lang != "zh":
        raise ValidationError(f"target_lang {target_lang!r} not supported")

    full_key = _full_cache_key(target_lang, article_id)
    try:
        raw = await redis.get(full_key)
    except Exception as e:
        log.warning("translate.full.redis_get_fail", err=str(e))
        raw = None
    if raw:
        try:
            obj = json.loads(raw)
            return {
                "id": article_id,
                "title": obj.get("title", ""),
                "summary": obj.get("summary", ""),
                "contentHtml": obj.get("contentHtml", ""),
                "cached": True,
            }
        except (json.JSONDecodeError, TypeError):
            pass

    art = (
        await db.execute(select(Article).where(Article.id == article_id))
    ).scalar_one_or_none()
    if art is None:
        raise ValidationError(f"article {article_id} not found")

    # Same-language no-op
    if str(art.lang) == target_lang:
        result = {
            "title": art.title,
            "summary": art.summary or "",
            "contentHtml": art.content_html or "",
        }
        await _store_full(redis, target_lang, article_id, result)
        return {"id": article_id, **result, "cached": False}

    # Pick a provider with a key
    cfg = await settings_service.read_settings(db, user_id)
    candidates = [cfg.default_provider, *cfg.configured_providers]
    provider: str | None = None
    api_key: str | None = None
    for cand in candidates:
        if cand not in ai_service.PROVIDER_FNS:
            continue
        k = await settings_service.get_provider_key(db, user_id, cand)
        if k:
            provider = cand
            api_key = k
            break
    if provider is None or api_key is None:
        raise ValidationError(
            "no AI provider key configured; add one in /settings before translating"
        )
    model_override = await settings_service.get_provider_model(db, user_id, provider)
    model = model_override or ai_service.DEFAULT_MODELS[provider]
    endpoint_override = await settings_service.get_provider_endpoint(db, user_id, provider)
    url = endpoint_override or ai_service.DEFAULT_ENDPOINTS[provider]

    body = (art.content_html or "").strip()
    truncated = False
    if len(body) > FULL_BODY_CHAR_LIMIT:
        body = body[:FULL_BODY_CHAR_LIMIT] + "\n<!-- truncated -->"
        truncated = True

    prompt = (
        FULL_TRANSLATION_PROMPT
        .replace("{title}", art.title or "")
        .replace("{summary}", (art.summary or "").strip())
        .replace("{content_html}", body)
    )

    log.info(
        "translate.full.start",
        provider=provider,
        model=model,
        article_id=article_id,
        body_chars=len(body),
        truncated=truncated,
    )
    try:
        text = await asyncio.wait_for(
            ai_service.PROVIDER_FNS[provider](
                prompt, api_key=api_key, model=model, url=url
            ),
            timeout=240,
        )
    except asyncio.TimeoutError as e:
        raise TranslationError(f"{provider} full-translate timed out after 240s") from e
    except httpx.HTTPError as e:
        raise TranslationError(f"{provider} network error: {e}") from e

    # Try delimiter-format first (more reliable for HTML), fall back to JSON
    parsed = _parse_delimited_translation(text or "")
    if parsed is None:
        obj = _extract_json_object(text or "")
        if obj:
            parsed = {
                "title": str(obj.get("title", "")).strip(),
                "summary": str(obj.get("summary", "")).strip(),
                "contentHtml": str(obj.get("contentHtml", "")).strip(),
            }

    title = (parsed or {}).get("title", "")
    summary = (parsed or {}).get("summary", "")
    content_html = (parsed or {}).get("contentHtml", "")

    if not title or not content_html:
        log.warning(
            "translate.full.empty_or_partial",
            provider=provider,
            text_len=len(text or ""),
            head=(text or "")[:300],
        )
        raise TranslationError(
            f"{provider} returned an empty / partial translation"
        )

    result = {"title": title, "summary": summary, "contentHtml": content_html}
    await _store_full(redis, target_lang, article_id, result)
    return {"id": article_id, **result, "cached": False}


def _full_cache_key(lang: str, article_id: int) -> str:
    return f"translation:{lang}:{article_id}:full"


async def _store_full(redis: Redis, lang: str, aid: int, payload: dict) -> None:
    try:
        await redis.set(
            _full_cache_key(lang, aid),
            json.dumps(payload, ensure_ascii=False),
            ex=CACHE_TTL_SECONDS,
        )
    except Exception as e:
        log.warning("translate.full.redis_set_fail", err=str(e), aid=aid)


_OBJECT_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def _extract_json_object(text: str) -> dict | None:
    if not text or not text.strip():
        return None
    text = text.strip()
    m = _OBJECT_FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    try:
        v = json.loads(text)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        s = text.find("{")
        e = text.rfind("}")
        if s >= 0 and e > s:
            try:
                v = json.loads(text[s : e + 1])
                if isinstance(v, dict):
                    return v
            except json.JSONDecodeError:
                pass
    return None


# ─── block-level (per-paragraph) translation ───
BLOCK_TRANSLATION_PROMPT = """\
你是专业新闻翻译。请把下面 {n} 个 HTML 块翻译成简体中文。

**译法规则**：
- 专有名词按主流中文媒体规范：Trump → 特朗普；Federal Reserve → 美联储；
  FT → 英国《金融时报》(FT)；Nikkei → 《日经》。
- 国际关系敏感议题严格中立客观，不引申、不暗示。
- 数字单位规范：100M USD → 1 亿美元；3% → 3%。

**HTML 处理**：
- 严格保留所有 HTML 标签 (<p>, <h2>, <a>, <img>, <strong>, <em>, <li>, <blockquote> 等)
- <a href="..."> 的 href 保持不变，只翻译链接显示文字
- <img src="..."> 的 src 保持不变，alt 文字可以翻译
- 不要新增 / 删除标签结构

**输出格式**：每个块的译文用下面标记包裹，标记一字不差，**不要 markdown 代码块**：

###[0]###
译文 0 的 HTML
###[1]###
译文 1 的 HTML
...
###END###

**待翻译**：
{blocks_input}
"""


def _block_cache_key(lang: str, sha: str) -> str:
    return f"translation:{lang}:block:{sha}"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_BLOCK_MARKER_RE = re.compile(r"###\s*\[\s*(\d+)\s*\]\s*###", re.MULTILINE)


def _parse_block_output(text: str, expected_n: int) -> list[str | None]:
    """Parse `###[N]###`-delimited output. Returns a list parallel to the
    requested blocks; None for blocks the model omitted."""
    out: list[str | None] = [None] * expected_n
    if not text or not text.strip():
        return out
    # Find all marker positions
    markers: list[tuple[int, int, int]] = []  # (start, end, idx)
    for m in _BLOCK_MARKER_RE.finditer(text):
        try:
            idx = int(m.group(1))
        except ValueError:
            continue
        markers.append((m.start(), m.end(), idx))
    if not markers:
        return out
    end_pos = text.find("###END###")
    for i, (start, end, idx) in enumerate(markers):
        if idx < 0 or idx >= expected_n:
            continue
        body_start = end
        body_end = markers[i + 1][0] if i + 1 < len(markers) else (
            end_pos if end_pos > body_start else len(text)
        )
        body = text[body_start:body_end].strip()
        if body:
            out[idx] = body
    return out


async def _translate_block_batch(
    *,
    blocks: list[tuple[int, str]],   # [(global_index, text), ...]
    provider: str,
    api_key: str,
    model: str,
    url: str,
) -> dict[int, str]:
    """Translate one batch of blocks. Returns { global_index: translated_text }
    for blocks the model successfully translated."""
    blocks_input = "\n".join(
        f"###[{local_i}]###\n{text}" for local_i, (_, text) in enumerate(blocks)
    )
    prompt = BLOCK_TRANSLATION_PROMPT.replace("{n}", str(len(blocks))).replace(
        "{blocks_input}", blocks_input
    )

    try:
        text = await asyncio.wait_for(
            ai_service.PROVIDER_FNS[provider](
                prompt, api_key=api_key, model=model, url=url
            ),
            timeout=180,
        )
    except asyncio.TimeoutError as e:
        raise TranslationError(f"{provider} block batch timed out") from e
    except httpx.HTTPError as e:
        raise TranslationError(f"{provider} network error: {e}") from e

    parsed = _parse_block_output(text or "", expected_n=len(blocks))
    out: dict[int, str] = {}
    for local_i, parsed_translation in enumerate(parsed):
        if not parsed_translation:
            continue
        global_i, original = blocks[local_i]
        # Drop echoes — if translation matches original, treat as untranslated
        if parsed_translation.strip() == original.strip():
            continue
        out[global_i] = parsed_translation
    return out


async def translate_blocks(
    redis: Redis,
    db: AsyncSession,
    *,
    user_id: UUID,
    texts: list[str],
    target_lang: str = "zh",
) -> tuple[list[str | None], list[bool]]:
    """Translate a list of HTML / text blocks. Cached per-block by content hash.

    Returns (translations, cached_flags) parallel to input. translations[i]
    is None if the model failed for that block (caller falls back to original)."""
    if target_lang != "zh":
        raise ValidationError(f"target_lang {target_lang!r} not supported")
    if not texts:
        return [], []

    # ── 1. Cache lookup ──
    hashes = [_sha(t) for t in texts]
    keys = [_block_cache_key(target_lang, h) for h in hashes]
    try:
        cached_raw = await redis.mget(keys)
    except Exception as e:
        log.warning("translate.blocks.redis_mget_fail", err=str(e))
        cached_raw = [None] * len(keys)

    out: list[str | None] = [None] * len(texts)
    cached_flags: list[bool] = [False] * len(texts)
    miss_indices: list[int] = []
    for i, raw in enumerate(cached_raw):
        if raw:
            out[i] = raw
            cached_flags[i] = True
        else:
            miss_indices.append(i)

    if not miss_indices:
        log.info("translate.blocks.all_cached", count=len(texts))
        return out, cached_flags

    # ── 2. Dedupe misses by hash so we don't translate dupes twice ──
    unique_misses: list[tuple[int, str]] = []  # (representative_index, text)
    seen_hash_to_idx: dict[str, int] = {}
    for i in miss_indices:
        h = hashes[i]
        if h in seen_hash_to_idx:
            continue
        seen_hash_to_idx[h] = i
        unique_misses.append((i, texts[i]))

    # ── 3. Pick provider ──
    cfg = await settings_service.read_settings(db, user_id)
    candidates = [cfg.default_provider, *cfg.configured_providers]
    provider: str | None = None
    api_key: str | None = None
    for cand in candidates:
        if cand not in ai_service.PROVIDER_FNS:
            continue
        k = await settings_service.get_provider_key(db, user_id, cand)
        if k:
            provider = cand
            api_key = k
            break
    if provider is None or api_key is None:
        raise ValidationError(
            "no AI provider key configured; add one in /settings before translating"
        )
    model_override = await settings_service.get_provider_model(db, user_id, provider)
    model = model_override or ai_service.DEFAULT_MODELS[provider]
    endpoint_override = await settings_service.get_provider_endpoint(db, user_id, provider)
    url = endpoint_override or ai_service.DEFAULT_ENDPOINTS[provider]

    # ── 4. Slice into BLOCKS_PER_CALL-sized batches ──
    batches = [
        unique_misses[i : i + BLOCKS_PER_CALL]
        for i in range(0, len(unique_misses), BLOCKS_PER_CALL)
    ]
    log.info(
        "translate.blocks.start",
        provider=provider,
        model=model,
        unique_misses=len(unique_misses),
        batches=len(batches),
        cache_hits=len(texts) - len(miss_indices),
    )

    results = await asyncio.gather(
        *[
            _translate_block_batch(
                blocks=b,
                provider=provider,
                api_key=api_key,
                model=model,
                url=url,
            )
            for b in batches
        ],
        return_exceptions=True,
    )

    # ── 5. Merge results back to per-index ──
    translated_by_idx: dict[int, str] = {}
    for r in results:
        if isinstance(r, Exception):
            log.warning("translate.blocks.batch_fail", err=str(r))
            continue
        translated_by_idx.update(r)

    # ── 6. Fan-out: assign each translated text to all positions sharing
    #     the same hash, and write to cache ──
    for global_i, translated in translated_by_idx.items():
        if not translated:
            continue
        target_hash = hashes[global_i]
        # write to cache
        try:
            await redis.set(
                _block_cache_key(target_lang, target_hash),
                translated,
                ex=CACHE_TTL_SECONDS,
            )
        except Exception as e:
            log.warning("translate.blocks.redis_set_fail", err=str(e))
        # fan out to all positions with this hash
        for j, h in enumerate(hashes):
            if h == target_hash and out[j] is None:
                out[j] = translated

    log.info(
        "translate.blocks.done",
        translated=len(translated_by_idx),
        cache_hits=sum(cached_flags),
    )
    return out, cached_flags


# ─── helpers ─────────────────────────────────────
def _cache_key(lang: str, article_id: int) -> str:
    return f"translation:{lang}:{article_id}"


async def _store(redis: Redis, lang: str, aid: int, title: str, summary: str) -> None:
    try:
        await redis.set(
            _cache_key(lang, aid),
            json.dumps({"title": title, "summary": summary}, ensure_ascii=False),
            ex=CACHE_TTL_SECONDS,
        )
    except Exception as e:
        log.warning("translate.redis_set_fail", err=str(e), aid=aid)


async def _translate_one_batch(
    *,
    articles: list[Article],
    provider: str,
    api_key: str,
    model: str,
    url: str,
    target_lang: str,
) -> dict[int, dict]:
    payload = [
        {
            "id": a.id,
            "lang": str(a.lang),
            "title": a.title,
            "summary": (a.summary or "").strip()[:500],
        }
        for a in articles
    ]
    prompt = TRANSLATION_PROMPT.replace(
        "{articles_json}", json.dumps(payload, ensure_ascii=False)
    )

    try:
        text = await asyncio.wait_for(
            ai_service.PROVIDER_FNS[provider](
                prompt, api_key=api_key, model=model, url=url
            ),
            timeout=180,
        )
    except asyncio.TimeoutError as e:
        raise TranslationError(f"{provider} translation timed out after 180s") from e
    except httpx.HTTPError as e:
        raise TranslationError(f"{provider} network error: {e}") from e

    if not text or not text.strip():
        log.warning(
            "translate.empty_response",
            provider=provider,
            model=model,
            n=len(articles),
            hint="provider may have hit max output tokens — try smaller MAX_BATCH",
        )
        return {}  # outer caller fills originals as fallback (without caching)
    try:
        parsed = _extract_json_array(text)
    except (ValueError, json.JSONDecodeError) as e:
        log.warning(
            "translate.parse_fail",
            provider=provider,
            err=str(e),
            head=text[:200],
        )
        return {}

    out: dict[int, dict] = {}
    expected_ids = {a.id for a in articles}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        aid = item.get("id")
        if not isinstance(aid, int) or aid not in expected_ids:
            continue
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not title:
            continue
        # Discard echoes — if the LLM just gave us the original back unchanged
        # for non-zh articles, treat as no translation so we don't cache it
        # and keep retrying next time.
        a = next((x for x in articles if x.id == aid), None)
        if a is not None and title == a.title and summary == (a.summary or "").strip():
            continue
        out[aid] = {"title": title, "summary": summary}

    return out


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def _extract_json_array(text: str) -> list:
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    try:
        v = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: locate first [ and matching last ]
        s = text.find("[")
        e = text.rfind("]")
        if s < 0 or e <= s:
            raise
        v = json.loads(text[s : e + 1])
    if not isinstance(v, list):
        raise ValueError(f"expected JSON array, got {type(v).__name__}")
    return v
