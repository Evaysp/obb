"""Exception hierarchy used across the app.

Per CONVENTIONS.md §4 and §6:
- All app errors inherit AppError so middleware can catch uniformly
- Fetcher errors split into transient / auth / not-found / blocked / extraction
  — this classification drives retry vs stop vs alert decisions
"""


# ─── app-level (API) ────────────────────────────
class AppError(Exception):
    """Base for all application errors. HTTP middleware catches this."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message or self.__class__.__name__)
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class AuthError(AppError):
    status_code = 401
    code = "auth_error"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"


# ─── fetcher-level ──────────────────────────────
class FetchError(Exception):
    """Base for all scraper errors. Subclasses drive retry policy."""


class TransientError(FetchError):
    """Network blip, 5xx, timeout — retry with backoff."""


class FetchAuthError(FetchError):
    """Cookie expired / 401 / paywall hit unauthenticated — do NOT retry, mark cookie stale."""


class FetchNotFoundError(FetchError):
    """404 — article was pulled or URL bad — skip, do not retry."""


class BlockedError(FetchError):
    """403 / 429 / CAPTCHA — downshift rate, alert, long backoff."""


class ExtractionError(FetchError):
    """Fetched HTML but parse failed — save raw HTML for debug, skip."""
