"""LangChain tools over the ScrapeWise REST API.

One tool per meaningful capability, not one per route. Routes that only make
sense to a human operator (schema publishing, desktop layout) are deliberately
absent -- a model with a tool that rewrites a schema version is a liability,
and `langchain_scrapewise` is read-biased by design. The one write tool here,
:class:`ScrapewiseRunScraperTool`, only starts a run; it cannot change
configuration.
"""

from __future__ import annotations

from typing import Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field

from .base import ScrapewiseBaseTool


# ----------------------------------------------------------------------
# argument schemas
# ----------------------------------------------------------------------


class NoArgsSchema(BaseModel):
    """Takes no arguments."""


class ScraperIdSchema(BaseModel):
    scraper_id: str = Field(
        ...,
        description=(
            "The scraper's id, as returned by scrapewise_list_scrapers. "
            "A 24-character hex ObjectId."
        ),
    )


class SampleDataSchema(BaseModel):
    scraper_id: str = Field(
        ..., description="The scraper's id, from scrapewise_list_scrapers."
    )
    prefer_persisted: bool = Field(
        default=False,
        description=(
            "Return the last stored rows instead of re-extracting. Faster, but "
            "the rows describe the PREVIOUS run, so do not use it to check a "
            "run you just started."
        ),
    )


class GroupIdSchema(BaseModel):
    group_id: str = Field(
        ...,
        description="The scraper group's id, from scrapewise_list_scraper_groups.",
    )


class GroupDataSchema(BaseModel):
    group_id: str = Field(
        ..., description="The scraper group's id, from scrapewise_list_scraper_groups."
    )
    page: int = Field(default=0, description="Zero-based page index.")
    size: int = Field(
        default=50,
        description="Rows per page, 1-200. Keep it small; rows are wide.",
        ge=1,
        le=200,
    )


class LoadHistorySchema(BaseModel):
    scraper_id: str = Field(
        ..., description="The scraper's id, from scrapewise_list_scrapers."
    )
    size: int = Field(
        default=5,
        description="How many of the most recent runs to return, 1-50.",
        ge=1,
        le=50,
    )


class SiteLinksSchema(BaseModel):
    site_id: str = Field(
        ...,
        description=(
            "The SITE id, from scrapewise_get_scraper_site. Passing a scraper "
            "id here returns an empty list, not an error."
        ),
    )
    page: int = Field(default=0, description="Zero-based page index.")
    size: int = Field(
        default=50, description="Links per page, 1-200.", ge=1, le=200
    )


class PreviewRuleSchema(BaseModel):
    rule: dict = Field(
        ...,
        description=(
            'A post-process rule object, e.g. {"postProcessKind": '
            '"NUMBER_EXTRACT"}. Dry-run only; nothing is saved.'
        ),
    )
    sample_value: str = Field(
        ..., description='One raw value to run the rule against, e.g. "12,90 EUR".'
    )


# ----------------------------------------------------------------------
# tools
# ----------------------------------------------------------------------


class ScrapewiseListScrapersTool(ScrapewiseBaseTool):
    """List the account's scrapers."""

    name: str = "scrapewise_list_scrapers"
    description: str = (
        "List every scraper on the ScrapeWise account, with id, name, group and "
        "last-run state. Start here when you need a scraper id. Note: this "
        "listing always reports schemaId as null, even for scrapers that have "
        "one -- use scrapewise_get_scraper to check a binding."
    )
    args_schema: Type[BaseModel] = NoArgsSchema

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._call(self.client.list_scrapers)


class ScrapewiseGetScraperTool(ScrapewiseBaseTool):
    """Fetch one scraper's full configuration."""

    name: str = "scrapewise_get_scraper"
    description: str = (
        "Get one ScrapeWise scraper's full configuration by id: source URL, "
        "field mapping, post-process rules, schema binding and last-run state. "
        "Use this to find out why a scraper produces the output it does."
    )
    args_schema: Type[BaseModel] = ScraperIdSchema

    def _run(
        self,
        scraper_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._call(self.client.get_scraper, scraper_id)


class ScrapewiseSampleDataTool(ScrapewiseBaseTool):
    """Read sample extracted rows for one scraper."""

    name: str = "scrapewise_get_sample_data"
    description: str = (
        "Read sample extracted product rows for one ScrapeWise scraper -- "
        "prices, titles, identifiers and whatever else its schema declares. "
        "Capped at 100 rows by the API, so never use the count it returns as a "
        "total; use scrapewise_get_run_history for real row counts."
    )
    args_schema: Type[BaseModel] = SampleDataSchema

    def _run(
        self,
        scraper_id: str,
        prefer_persisted: bool = False,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._call(
            self.client.get_sample_data,
            scraper_id,
            prefer_persisted=prefer_persisted or None,
        )


class ScrapewiseRunScraperTool(ScrapewiseBaseTool):
    """Start a run of one scraper."""

    name: str = "scrapewise_run_scraper"
    description: str = (
        "Start a scrape run for one ScrapeWise scraper. Returns immediately -- "
        "the run is asynchronous, so poll scrapewise_get_run_history for the "
        "outcome. Fails with 'disabled or already RUNNING/PENDING' if the "
        "scraper is already queued or is not runnable."
    )
    args_schema: Type[BaseModel] = ScraperIdSchema

    def _run(
        self,
        scraper_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._call(self.client.run_scraper, scraper_id)


class ScrapewiseRunHistoryTool(ScrapewiseBaseTool):
    """Read recent runs of one scraper."""

    name: str = "scrapewise_get_run_history"
    description: str = (
        "Read the recent run history of one ScrapeWise scraper: rows stored "
        "(itemsQuantity), pages attempted, total requests, stop reason and "
        "error message. This is the authority on how many rows a run produced."
    )
    args_schema: Type[BaseModel] = LoadHistorySchema

    def _run(
        self,
        scraper_id: str,
        size: int = 5,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._call(
            self.client.get_load_history, scraper_id, page=0, size=size
        )


class ScrapewiseListGroupsTool(ScrapewiseBaseTool):
    """List the account's scraper groups."""

    name: str = "scrapewise_list_scraper_groups"
    description: str = (
        "List every ScrapeWise scraper group. A group bundles the scrapers "
        "that monitor one market or one competitor set, and is the unit that "
        "price comparison and data export work on."
    )
    args_schema: Type[BaseModel] = NoArgsSchema

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._call(self.client.list_groups)


class ScrapewiseGroupDataTool(ScrapewiseBaseTool):
    """Read one page of a group's collected rows."""

    name: str = "scrapewise_get_group_data"
    description: str = (
        "Read collected product rows for a whole ScrapeWise scraper group, one "
        "page at a time. This is the cross-competitor dataset: the same "
        "products as seen on every site in the group. Ask for small pages; the "
        "rows are wide."
    )
    args_schema: Type[BaseModel] = GroupDataSchema

    def _run(
        self,
        group_id: str,
        page: int = 0,
        size: int = 50,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._call(
            self.client.get_group_data, group_id, page=page, size=size
        )


class ScrapewiseGetScraperSiteTool(ScrapewiseBaseTool):
    """Get the site document id and link count for one scraper."""

    name: str = "scrapewise_get_scraper_site"
    description: str = (
        "Get the site document for one ScrapeWise scraper: its site id and how "
        "many product links it holds. The links themselves are not included -- "
        "pass the returned site id to scrapewise_list_site_links."
    )
    args_schema: Type[BaseModel] = ScraperIdSchema

    def _run(
        self,
        scraper_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._call(self.client.get_scraper_site, scraper_id)


class ScrapewiseSiteLinksTool(ScrapewiseBaseTool):
    """List the product links a site will scrape."""

    name: str = "scrapewise_list_site_links"
    description: str = (
        "List the product URLs one ScrapeWise site will scrape, paginated. "
        "Each link carries a title that is usually the product identifier the "
        "row gets stamped with. Takes a SITE id from "
        "scrapewise_get_scraper_site, not a scraper id."
    )
    args_schema: Type[BaseModel] = SiteLinksSchema

    def _run(
        self,
        site_id: str,
        page: int = 0,
        size: int = 50,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._call(
            self.client.list_site_links, site_id, page=page, size=size
        )


class ScrapewiseGroupRulesTool(ScrapewiseBaseTool):
    """Read a group's post-process rules."""

    name: str = "scrapewise_get_group_rules"
    description: str = (
        "Read the post-process rules for one ScrapeWise scraper group -- the "
        "transforms applied to raw extracted values, such as number "
        "extraction, currency conversion and quantity normalisation. Read-only."
    )
    args_schema: Type[BaseModel] = GroupIdSchema

    def _run(
        self,
        group_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._call(self.client.get_group_post_process_rules, group_id)


class ScrapewisePreviewRuleTool(ScrapewiseBaseTool):
    """Dry-run one post-process rule against one value."""

    name: str = "scrapewise_preview_rule"
    description: str = (
        "Dry-run one ScrapeWise post-process rule against a single sample "
        "value and see what it returns. Nothing is saved. Use this to work out "
        "the right rule for a messy price string before touching a group's "
        "configuration."
    )
    args_schema: Type[BaseModel] = PreviewRuleSchema

    def _run(
        self,
        rule: dict,
        sample_value: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._call(self.client.preview_rule, rule, sample_value)


class ScrapewiseListSchemasTool(ScrapewiseBaseTool):
    """List the account's extraction schemas."""

    name: str = "scrapewise_list_schemas"
    description: str = (
        "List the ScrapeWise extraction schemas on the account. A schema "
        "declares the fields the AI extractor emits. Metadata only -- the "
        "field list is not included."
    )
    args_schema: Type[BaseModel] = NoArgsSchema

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return self._call(self.client.list_customer_schemas)


SCRAPEWISE_TOOL_CLASSES = (
    ScrapewiseListScrapersTool,
    ScrapewiseGetScraperTool,
    ScrapewiseSampleDataTool,
    ScrapewiseRunScraperTool,
    ScrapewiseRunHistoryTool,
    ScrapewiseListGroupsTool,
    ScrapewiseGroupDataTool,
    ScrapewiseGetScraperSiteTool,
    ScrapewiseSiteLinksTool,
    ScrapewiseGroupRulesTool,
    ScrapewisePreviewRuleTool,
    ScrapewiseListSchemasTool,
)
"""Every tool class in this package, in a stable order."""


__all__ = [
    "SCRAPEWISE_TOOL_CLASSES",
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
]
