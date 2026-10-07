"""A toolkit that hands an agent every ScrapeWise tool over one client."""

from __future__ import annotations

from typing import Any, List, Optional

from langchain_core.tools import BaseTool
from langchain_core.tools.base import BaseToolkit
from pydantic import Field, PrivateAttr
from scrapewise import ScrapewiseClient

from .tools import SCRAPEWISE_TOOL_CLASSES


class ScrapewiseToolkit(BaseToolkit):
    """Every ScrapeWise tool, sharing one connection pool.

    Constructing the tools individually works and is fine for one or two, but
    each one then opens its own ``httpx.Client``. The toolkit builds a single
    client and injects it, which matters once an agent holds a dozen tools.

    The client is held on a private attribute rather than a validated field,
    matching :class:`~langchain_scrapewise.base.ScrapewiseBaseTool`. That keeps
    it out of ``model_dump()`` -- it holds the API key -- and lets a test double
    or a subclass stand in for the real client.

    Example:
        >>> toolkit = ScrapewiseToolkit(api_key="YOUR_SCRAPEWISE_API_KEY")
        >>> len(toolkit.get_tools())
        12
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

    def __init__(
        self, client: Optional[ScrapewiseClient] = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._client = client

    @property
    def client(self) -> ScrapewiseClient:
        """The lazily constructed API client shared by every tool."""
        if self._client is None:
            init: dict = {}
            if self.api_key is not None:
                init["api_key"] = self.api_key
            if self.base_url is not None:
                init["base_url"] = self.base_url
            if self.timeout is not None:
                init["timeout"] = self.timeout
            self._client = ScrapewiseClient(**init)
        return self._client

    def get_tools(self) -> List[BaseTool]:
        """Return one instance of every tool in this package."""
        shared = self.client
        return [cls(client=shared) for cls in SCRAPEWISE_TOOL_CLASSES]


__all__ = ["ScrapewiseToolkit"]
