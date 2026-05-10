"""Small helpers used in multiple places.

Per CONVENTIONS.md §6:
- canonicalize_url strips utm_* and fragments before hashing for dedup
- url_hash is sha256 hex of the canonical form
"""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_STRIP_PARAM_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "_ga", "ref_")


def canonicalize_url(url: str) -> str:
    """Drop tracking params, lowercase host, strip fragment and trailing slash."""
    parsed = urlparse(url.strip())
    host = parsed.hostname or ""
    netloc = host.lower()
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{netloc}:{parsed.port}"

    params = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if not any(k.lower().startswith(p) for p in _STRIP_PARAM_PREFIXES)
    ]
    query = urlencode(sorted(params))

    path = parsed.path or "/"
    # drop trailing slash except for root
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


def url_hash(url: str) -> str:
    """sha256 hex of the canonical URL — used as unique index for dedup."""
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()


def content_hash(text: str) -> str:
    """sha256 hex of normalized text — collapse whitespace, strip."""
    normalized = " ".join(text.split()).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
