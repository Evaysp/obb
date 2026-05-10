"""Content extraction and sanitization.

Per CONVENTIONS.md §3 and §6:
- Every extracted HTML passes through a strict bleach allowlist before DB insert
- Frontend trusts the DB contents — this is the only gate
- trafilatura handles the messy parts (boilerplate removal, date extraction)
"""

from __future__ import annotations

from urllib.parse import urljoin

import bleach
import trafilatura
from bs4 import BeautifulSoup

ALLOWED_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote",
    "em", "strong", "i", "b", "u", "s", "small", "sub", "sup",
    "a", "br", "hr",
    "code", "pre",
    "img", "figure", "figcaption",
    "span",
}
ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
    "span": ["class"],
}
ALLOWED_PROTOCOLS = {"http", "https", "mailto"}


def extract(html: str, url: str) -> dict | None:
    """Run trafilatura + bleach. Returns a dict with keys ready to build ArticleDoc, or None."""
    meta = trafilatura.bare_extraction(
        html,
        url=url,
        include_images=True,
        include_links=True,
        with_metadata=True,
        output_format="python",
    )
    if not meta:
        return None

    raw_html = trafilatura.extract(
        html,
        output_format="html",
        include_images=True,
        include_links=True,
    ) or ""

    raw_html = _absolutize_urls(raw_html, url)
    clean_html = bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    clean_html = bleach.linkify(clean_html, skip_tags=["pre", "code"])

    text = meta.get("text") or ""
    reading_time = max(1, len(text.split()) // 220) if text else None

    return {
        "title": meta.get("title") or "",
        "author": meta.get("author"),
        "published_at": meta.get("date"),
        "summary": (meta.get("description") or _first_paragraph(text)).strip()[:600],
        "content_html": clean_html,
        "content_text": text,
        "lead_image_url": meta.get("image"),
        "reading_time_min": reading_time,
    }


def _first_paragraph(text: str) -> str:
    for block in text.split("\n"):
        block = block.strip()
        if len(block) > 40:
            return block
    return text[:400]


def _absolutize_urls(html: str, base_url: str) -> str:
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for tag, attr in (("a", "href"), ("img", "src")):
        for el in soup.find_all(tag):
            val = el.get(attr)
            if val and not val.startswith(("http://", "https://", "mailto:", "#")):
                el[attr] = urljoin(base_url, val)
    return str(soup)
