"""Financial Times fetcher — homepage scrape for discovery + cookie-authenticated article fetch.

Mirrors the Nikkei pattern: pull www.ft.com homepage, harvest /content/<id>
links, then hit each URL with the user's cookies attached.

Per CONVENTIONS.md §6:
- FetchAuthError on login redirect / suspiciously short body — caller
  marks the cookie row stale, doesn't retry
- BlockedError on 403 / 429
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from dateutil import parser as dateparser

from app.core.config import get_settings
from app.core.errors import (
    BlockedError,
    ExtractionError,
    FetchAuthError,
    FetchNotFoundError,
    TransientError,
)
from app.core.logging import get_logger
from app.models.base import Lang
from workers.extract import extract
from workers.fetchers.base import ArticleDoc, BaseFetcher

log = get_logger("fetcher.ft")

# FT's homepage is heavily anti-bot-protected (Akamai). The RSS endpoints
# under /<section>?format=rss respond cleanly without challenge. The article
# pages themselves still need cookies, but discovery is now robust.
DEFAULT_HOME = "https://www.ft.com/world?format=rss"

# FT article URLs follow /content/<uuid> — e.g.
# https://www.ft.com/content/abcd1234-5678-90ab-cdef-1234567890ab
ARTICLE_LINK_RE = re.compile(
    r"^https?://(?:www\.)?ft\.com/content/[A-Za-z0-9][A-Za-z0-9-]+/?$"
)

DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class FTFetcher(BaseFetcher):
    needs_cookies = True
    rate_limit_per_min = 4

    def __init__(
        self,
        slug: str,
        lang: Lang = Lang.en,
        *,
        cookies: list[dict] | None = None,
        user_agent: str | None = None,
        feed_url: str | None = None,
    ) -> None:
        self.slug = slug
        self.lang = lang
        self.feed_url = feed_url or DEFAULT_HOME
        self._cookies = cookies or []
        self._ua = user_agent or DESKTOP_UA

    # ── helpers ────────────────────────────────
    def _cookie_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for c in self._cookies:
            name = c.get("name")
            value = c.get("value")
            if isinstance(name, str) and isinstance(value, str):
                out[name] = value
        return out

    def _client(self) -> httpx.AsyncClient:
        settings = get_settings()
        return httpx.AsyncClient(
            headers={
                "User-Agent": self._ua,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
            },
            cookies=self._cookie_dict() or None,
            timeout=settings.fetch_timeout_seconds,
            follow_redirects=True,
        )

    # ── BaseFetcher API ────────────────────────
    async def discover(self) -> list[str]:
        # Discovery uses a no-auth-needed endpoint. Try RSS first (works against
        # FT's anti-bot CDN); HTML homepage falls back behind it just in case.
        try:
            async with self._client() as client:
                r = await client.get(self.feed_url)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in (403, 429):
                raise BlockedError(f"discover blocked {code}") from e
            raise TransientError(f"discover status {code}") from e
        except httpx.RequestError as e:
            raise TransientError(f"discover request failed: {e}") from e

        text = r.text
        ctype = r.headers.get("content-type", "").lower()
        is_rss = (
            "xml" in ctype
            or "rss" in ctype
            or text.lstrip().startswith(("<?xml", "<rss"))
        )

        urls: list[str] = []
        seen: set[str] = set()

        if is_rss:
            parsed = feedparser.parse(r.content)
            for entry in parsed.entries:
                href = getattr(entry, "link", None)
                if not href:
                    continue
                clean = href.split("?")[0].rstrip("/")
                if (ARTICLE_LINK_RE.match(clean + "/") or ARTICLE_LINK_RE.match(clean)) and clean not in seen:
                    seen.add(clean)
                    urls.append(clean)
        else:
            soup = BeautifulSoup(text, "html.parser")
            for a in soup.find_all("a", href=True):
                full = urljoin(self.feed_url, a["href"]).split("?")[0].rstrip("/")
                if (ARTICLE_LINK_RE.match(full + "/") or ARTICLE_LINK_RE.match(full)) and full not in seen:
                    seen.add(full)
                    urls.append(full)

        log.info(
            "ft.discover",
            count=len(urls),
            mode="rss" if is_rss else "html",
            authenticated=bool(self._cookies),
        )
        return urls

    async def fetch_article(
        self,
        url: str,
        cookies: list[dict] | None = None,  # noqa: ARG002 — kept for BaseFetcher compat
    ) -> ArticleDoc:
        # FT's Akamai bot manager TLS-fingerprints httpx and serves 403.
        # curl_cffi impersonates real Chrome's TLS handshake — same auth
        # cookies suddenly work. Use it ONLY for FT article pages; RSS
        # discovery is fine on httpx.
        settings = get_settings()
        try:
            r = await curl_requests.AsyncSession(
                impersonate="chrome131",
                timeout=settings.fetch_timeout_seconds,
                headers={
                    "User-Agent": self._ua,
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,"
                        "image/avif,image/webp,*/*;q=0.8"
                    ),
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                },
                cookies=self._cookie_dict() or None,
            ).get(url, allow_redirects=True)
        except Exception as e:
            raise TransientError(f"request failed: {e}") from e

        final_url = str(r.url)
        if (
            "id.ft.com" in final_url
            or "accounts.ft.com" in final_url
            or "/products" in final_url
            or "/login" in final_url
        ):
            raise FetchAuthError(f"redirected to login: {final_url}")

        if r.status_code == 404:
            raise FetchNotFoundError(f"404 at {url}")
        if r.status_code == 401:
            raise FetchAuthError(f"401 at {url}")
        if r.status_code == 403:
            raise BlockedError(f"403 at {url}")
        if r.status_code == 429:
            raise BlockedError(f"429 at {url}")
        if r.status_code >= 500:
            raise TransientError(f"upstream {r.status_code}")
        if r.status_code >= 400:
            raise ExtractionError(f"unexpected status {r.status_code}")

        doc = extract(r.text, url)
        if not doc or not doc.get("title"):
            raise ExtractionError(f"extraction empty for {url}")

        content_text = doc.get("content_text") or ""
        # FT serves a short preview to logged-out / expired sessions even with 200.
        # If we sent cookies but body is suspiciously short, treat as auth failure.
        if self._cookies and len(content_text) < 300:
            raise FetchAuthError(
                f"content too short ({len(content_text)} chars), cookies likely expired"
            )

        return ArticleDoc(
            url=url,
            title=doc["title"],
            summary=doc["summary"],
            content_html=doc["content_html"],
            content_text=doc["content_text"],
            author=doc["author"],
            published_at=_parse_date(doc.get("published_at")),
            lang=self.lang,
            lead_image_url=doc["lead_image_url"],
            reading_time_min=doc["reading_time_min"],
        )


def _parse_date(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        dt = dateparser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
