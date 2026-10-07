"""LangChain tools for the ScrapeWise web-scraping and price-monitoring API.

Quickstart::

    from langchain_scrapewise import ScrapewiseToolkit

    tools = ScrapewiseToolkit(api_key="YOUR_SCRAPEWISE_API_KEY").get_tools()
    llm_with_tools = llm.bind_tools(tools)
"""

from __future__ import annotations

from .base import ScrapewiseBaseTool
from .toolkit import ScrapewiseToolkit
from .tools import (
    SCRAPEWISE_TOOL_CLASSES,
    ScrapewiseGetScraperSiteTool,
    ScrapewiseGetScraperTool,
    ScrapewiseGroupDataTool,
    ScrapewiseGroupRulesTool,
    ScrapewiseListGroupsTool,
    ScrapewiseListSchemasTool,
    ScrapewiseListScrapersTool,
    ScrapewisePreviewRuleTool,
    ScrapewiseRunHistoryTool,
    ScrapewiseRunScraperTool,
    ScrapewiseSampleDataTool,
    ScrapewiseSiteLinksTool,
)

__version__ = "0.1.0"

__all__ = [
    "SCRAPEWISE_TOOL_CLASSES",
    "ScrapewiseBaseTool",
    "ScrapewiseGetScraperSiteTool",
    "ScrapewiseGetScraperTool",
    "ScrapewiseGroupDataTool",
    "ScrapewiseGroupRulesTool",
    "ScrapewiseListGroupsTool",
    "ScrapewiseListSchemasTool",
    "ScrapewiseListScrapersTool",
    "ScrapewisePreviewRuleTool",
    "ScrapewiseRunHistoryTool",
    "ScrapewiseRunScraperTool",
    "ScrapewiseSampleDataTool",
    "ScrapewiseSiteLinksTool",
    "ScrapewiseToolkit",
    "__version__",
]
