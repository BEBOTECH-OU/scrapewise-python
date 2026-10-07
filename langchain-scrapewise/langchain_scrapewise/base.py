"""Shared plumbing for the ScrapeWise LangChain tools."""

from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.tools import BaseTool
from pydantic import Field, PrivateAttr
from scrapewise import ScrapewiseClient, ScrapewiseError

MAX_CHARS = 12_000
"""Hard cap on a tool's returned string.

Group data and page HTML are routinely megabytes. Handing that back unbounded
either blows the model's context window or silently truncates in the middle of
a JSON document, which reads to the model as corrupt data rather than as a
limit. Truncating here, explicitly and with a visible marker, is the lesser
failure.
"""


class ScrapewiseBaseTool(BaseTool):
    """Base class holding one :class:`~scrapewise.ScrapewiseClient`.

    Pass ``client=`` to share a configured client (recommended when an agent
    gets several of these tools), or pass ``api_key=`` / rely on the
    ``SCRAPEWISE_API_KEY`` environment variable and let each tool build its
    own.
    """

    api_key: Optional[str] = Field(
        default=None,
        description="ScrapeWise API key. Falls back to $SCRAPEWISE_API_KEY.",
        exclude=True,
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Override the API root. Falls back to $SCRAPEWISE_BASE_URL.",
    )
    timeout: Optional[float] = Field(
        default=None, description="Per-request timeout in seconds."
    )

    _client: Optional[ScrapewiseClient] = PrivateAttr(default=None)

    def __init__(self, client: Optional[ScrapewiseClient] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = client

    @property
    def client(self) -> ScrapewiseClient:
        """The lazily constructed API client.

        Built on first use rather than in ``__init__`` so that importing a
        module full of tools cannot fail on a missing key, and so that a tool
        can be declared in config before credentials are present.
        """
        if self._client is None:
            kwargs: dict = {}
            if self.api_key is not None:
                kwargs["api_key"] = self.api_key
            if self.base_url is not None:
                kwargs["base_url"] = self.base_url
            if self.timeout is not None:
                kwargs["timeout"] = self.timeout
            self._client = ScrapewiseClient(**kwargs)
        return self._client

    # ------------------------------------------------------------------
    # response shaping
    # ------------------------------------------------------------------

    @staticmethod
    def _dump(value: Any) -> str:
        """Render an API payload as JSON text, capped at :data:`MAX_CHARS`."""
        text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
        if len(text) <= MAX_CHARS:
            return text
        return (
            text[:MAX_CHARS]
            + f"\n... [truncated at {MAX_CHARS} characters; narrow the request]"
        )

    def _call(self, fn: Any, *args: Any, **kwargs: Any) -> str:
        """Run one client call and return JSON text, or a readable error.

        A raised exception inside a tool aborts the agent run. Returning the
        failure as text lets the model correct a bad id or an over-wide request
        on its own, which is almost always what you want from a read tool.
        """
        try:
            return self._dump(fn(*args, **kwargs))
        except ScrapewiseError as exc:
            return self._dump(
                {
                    "error": type(exc).__name__,
                    "status": exc.status_code,
                    "message": str(exc),
                }
            )


__all__ = ["MAX_CHARS", "ScrapewiseBaseTool"]
