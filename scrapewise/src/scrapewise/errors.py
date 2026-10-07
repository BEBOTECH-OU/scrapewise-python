"""Exception hierarchy for the Scrapewise REST client.

Every error raised by :class:`scrapewise.ScrapewiseClient` is a
:class:`ScrapewiseError`, so a caller can catch exactly one type. The subclasses
exist so a caller *can* branch on the failure class without parsing strings.

The platform maps customer-level validation failures onto HTTP 400 with a JSON
body rather than onto a dedicated status, so ``ScrapewiseBadRequestError`` is
the one most callers actually hit. The raw body is always preserved on ``.body``
because the server's message is frequently the only diagnostic available --
several distinct platform errors share a single status code and are told apart
purely by their text.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type


class ScrapewiseError(Exception):
    """Base class for every error raised by this package.

    Attributes:
        message: Human-readable summary.
        status_code: HTTP status returned by the API, or ``None`` for transport
            failures (timeout, DNS, connection reset) where no response arrived.
        body: Verbatim response body as text. Empty string when there was no
            response. Never truncated -- platform diagnostics live here.
        method: HTTP method of the failed request.
        url: Full URL of the failed request.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        body: str = "",
        method: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.body = body
        self.method = method
        self.url = url

    @property
    def payload(self) -> Optional[Any]:
        """The response body parsed as JSON, or ``None`` if it was not JSON.

        Returns ``None`` rather than raising, because error bodies produced by
        the gateway rather than by the application are sometimes HTML.
        """
        if not self.body:
            return None
        try:
            return json.loads(self.body)
        except ValueError:
            return None

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code is not None:
            parts.append(f"(HTTP {self.status_code})")
        if self.method and self.url:
            parts.append(f"{self.method} {self.url}")
        if self.body:
            snippet = self.body if len(self.body) <= 500 else self.body[:500] + "..."
            parts.append(f"body={snippet}")
        return " ".join(parts)


class ScrapewiseConfigurationError(ScrapewiseError):
    """Raised before any request is made, e.g. no API key could be resolved."""


class ScrapewiseTransportError(ScrapewiseError):
    """No HTTP response arrived: connection error, DNS failure, reset."""


class ScrapewiseTimeoutError(ScrapewiseTransportError):
    """The request exceeded the configured timeout.

    Worth its own class: :meth:`scrapewise.ScrapewiseClient.load_site`
    legitimately runs for minutes on large pages, so a timeout there is a
    client-side budget problem rather than a missing route.
    """


class ScrapewiseAPIError(ScrapewiseError):
    """A response arrived with a non-2xx status."""


class ScrapewiseAuthError(ScrapewiseAPIError):
    """HTTP 401/403. The key is missing, malformed, revoked or out of scope.

    The platform expects ``Authorization: Bearer <key>``; an ``X-API-KEY``
    header returns 401.
    """


class ScrapewiseBadRequestError(ScrapewiseAPIError):
    """HTTP 400. Customer-level validation failures map to this status.

    The message in ``.body`` is the diagnostic -- unrelated causes share the
    status code.
    """


class ScrapewiseNotFoundError(ScrapewiseAPIError):
    """HTTP 404. Either the id does not exist or the path does not exist.

    Those two cases are not distinguishable from the status alone.
    """


class ScrapewiseConflictError(ScrapewiseAPIError):
    """HTTP 409. An optimistic-concurrency check failed.

    Returned by the group post-process-rules update when the supplied
    ``expected_version`` does not match the stored version.
    """


class ScrapewiseRateLimitError(ScrapewiseAPIError):
    """HTTP 429. Rate limiting on this platform is global, not per-endpoint."""


class ScrapewiseServerError(ScrapewiseAPIError):
    """HTTP 5xx."""


_STATUS_MAP: Dict[int, Type[ScrapewiseAPIError]] = {
    400: ScrapewiseBadRequestError,
    401: ScrapewiseAuthError,
    403: ScrapewiseAuthError,
    404: ScrapewiseNotFoundError,
    409: ScrapewiseConflictError,
    429: ScrapewiseRateLimitError,
}


def error_for_status(
    status_code: int,
    *,
    body: str,
    method: str,
    url: str,
) -> ScrapewiseAPIError:
    """Map an HTTP status onto the most specific error class available."""
    cls = _STATUS_MAP.get(status_code)
    if cls is None:
        cls = ScrapewiseServerError if status_code >= 500 else ScrapewiseAPIError
    return cls(
        f"Scrapewise API request failed with status {status_code}",
        status_code=status_code,
        body=body,
        method=method,
        url=url,
    )


__all__ = [
    "ScrapewiseAPIError",
    "ScrapewiseAuthError",
    "ScrapewiseBadRequestError",
    "ScrapewiseConfigurationError",
    "ScrapewiseConflictError",
    "ScrapewiseError",
    "ScrapewiseNotFoundError",
    "ScrapewiseRateLimitError",
    "ScrapewiseServerError",
    "ScrapewiseTimeoutError",
    "ScrapewiseTransportError",
    "error_for_status",
]
