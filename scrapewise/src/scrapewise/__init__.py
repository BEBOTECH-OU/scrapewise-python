"""Thin, dependency-light Python client for the ScrapeWise REST API.

Quickstart::

    from scrapewise import ScrapewiseClient

    with ScrapewiseClient(api_key="YOUR_SCRAPEWISE_API_KEY") as sw:
        for scraper in sw.list_scrapers():
            print(scraper["id"], scraper.get("name"))

Every method on :class:`~scrapewise.client.ScrapewiseClient` maps to exactly one
documented ScrapeWise REST route. No route is synthesised or guessed.
"""

from __future__ import annotations

from .client import (
    API_KEY_ENV_VAR,
    BASE_URL_ENV_VAR,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    LOAD_SITE_TIMEOUT,
    ScrapewiseClient,
)
from .errors import (
    ScrapewiseAPIError,
    ScrapewiseAuthError,
    ScrapewiseBadRequestError,
    ScrapewiseConfigurationError,
    ScrapewiseConflictError,
    ScrapewiseError,
    ScrapewiseNotFoundError,
    ScrapewiseRateLimitError,
    ScrapewiseServerError,
    ScrapewiseTimeoutError,
    ScrapewiseTransportError,
)
from .types import (
    CustomerSchema,
    CustomerSchemaSummary,
    DataRow,
    Desktop,
    GroupPostProcessRules,
    LoadHistoryEntry,
    Page,
    PostProcessRule,
    PreviewRuleResult,
    Scraper,
    ScraperConfig,
    ScraperGroup,
    ScraperSite,
    SiteLink,
)

__version__ = "0.1.0"

__all__ = [
    "API_KEY_ENV_VAR",
    "BASE_URL_ENV_VAR",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "LOAD_SITE_TIMEOUT",
    "CustomerSchema",
    "CustomerSchemaSummary",
    "DataRow",
    "Desktop",
    "GroupPostProcessRules",
    "LoadHistoryEntry",
    "Page",
    "PostProcessRule",
    "PreviewRuleResult",
    "Scraper",
    "ScraperConfig",
    "ScraperGroup",
    "ScraperSite",
    "ScrapewiseAPIError",
    "ScrapewiseAuthError",
    "ScrapewiseBadRequestError",
    "ScrapewiseClient",
    "ScrapewiseConfigurationError",
    "ScrapewiseConflictError",
    "ScrapewiseError",
    "ScrapewiseNotFoundError",
    "ScrapewiseRateLimitError",
    "ScrapewiseServerError",
    "ScrapewiseTimeoutError",
    "ScrapewiseTransportError",
    "SiteLink",
    "__version__",
]
