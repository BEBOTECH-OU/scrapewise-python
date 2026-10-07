"""Typed shapes for the Scrapewise REST responses.

These are ``TypedDict`` definitions, not models: every one is declared
``total=False`` and none of them validates anything at runtime. That is
deliberate.

The platform returns DTOs that are wider than any one caller needs, that differ
between the list projection and the single-entity projection of the same object,
and that nest most scraper configuration under ``config``. Validating against a
closed model would turn an additive backend change into a client-side crash. The
``TypedDict`` gives editors and type-checkers something to work with while the
runtime value stays a plain ``dict`` that always round-trips whatever the server
sent.

Two shape facts worth knowing before you index into these:

* Paginated payloads key their rows on ``content``, not ``items``.
* ``Scraper`` keeps ``itemsConfig`` / ``postProcessRules`` / ``sourceConfig`` /
  ``startType`` / ``timeout`` under ``config``, so there are no top-level keys
  with those names. Reading ``scraper["postProcessRules"]`` on a healthy
  scraper raises ``KeyError``; read ``scraper["config"]["postProcessRules"]``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

#: A single extracted product row. Column names are chosen by the scraper's
#: ``mapping`` / schema, so the shape is per-scraper and cannot be typed further.
#: Note the platform also injects ``title``, ``url``, ``_sw_scraper``,
#: ``_sw_group``, ``_sw_run_date`` and ``_sw_run_time`` columns.
DataRow = Dict[str, Any]

#: A post-process rule. Shape is
#: ``{kind, sourceField, outputField, outputType, params, overwritesRawField}``.
PostProcessRule = Dict[str, Any]


class Page(TypedDict, total=False):
    """A paginated envelope.

    The rows are under ``content``. Asking for ``items`` returns nothing on
    every paginated route this client touches.
    """

    content: List[Any]
    page: int
    size: int
    totalElements: int
    totalPages: int


class ScraperConfig(TypedDict, total=False):
    """The nested ``config`` block of a scraper DTO."""

    type: str
    timeout: int
    itemsConfig: List[Dict[str, Any]]
    postProcessRules: List[PostProcessRule]
    sourceConfig: Dict[str, Any]
    startType: str
    error: Optional[str]


class Scraper(TypedDict, total=False):
    """A scraper DTO.

    ``type`` (top level) selects the extraction engine and is one of
    ``SINGLE_PRODUCT`` / ``MULTIPLE_PRODUCTS`` / ``APPLICATION_LD_JSON`` /
    ``API`` / ``FILE``. ``config["type"]`` is a *different* field with the same
    name that holds ``ADVANCED`` or ``SIMPLE``.

    ``schemaId`` is omitted entirely by the list projection -- it reads as
    ``None`` for every scraper there even when the single-entity projection
    shows a binding. Do not use the list route to answer "is anything bound to
    this schema".
    """

    id: str
    name: str
    type: str
    groupId: Optional[str]
    schemaId: Optional[str]
    manual: bool
    siteMap: bool
    mapping: Dict[str, str]
    lastRun: Optional[str]
    lastRunState: Optional[str]
    shouldUseJavaScript: bool
    config: ScraperConfig


class ScraperGroup(TypedDict, total=False):
    """A scraper group DTO (the customer's site group)."""

    id: str
    name: str
    displayCurrency: Optional[str]
    scrapers: List[Scraper]


class ScraperSite(TypedDict, total=False):
    """The site document attached to a scraper.

    ``links`` is ``None`` on this route even when the site has links; read them
    with :meth:`scrapewise.ScrapewiseClient.list_site_links`, which is keyed on
    ``id`` from here (the *site* id), not on the scraper id.
    """

    id: str
    scraperId: str
    linkCount: int
    links: Optional[List["SiteLink"]]


class SiteLink(TypedDict, total=False):
    """One link in a site's link list."""

    url: str
    title: str


class LoadHistoryEntry(TypedDict, total=False):
    """One run of one scraper.

    ``itemsQuantity`` is the authoritative per-run row count. Do not count rows
    from sample data, which is capped.
    """

    id: str
    scraperId: str
    jobId: Optional[str]
    state: Optional[str]
    itemsQuantity: Optional[int]
    totalRequests: Optional[int]
    attempted: Optional[int]
    notAttempted: Optional[int]
    duration: Optional[int]
    stopReason: Optional[str]
    errorMessage: Optional[str]
    costLines: Optional[List[Dict[str, Any]]]


class CustomerSchemaSummary(TypedDict, total=False):
    """A row from the customer schema list.

    Metadata only: this route returns no ``content`` and no ``name``. Fetch the
    full document by id to see what a schema declares.

    ``groupId`` here is a hyphenated UUID identifying a schema *version family*
    -- not a scraper group, whose id is a Mongo ObjectId. The id shape is how
    you tell the two apart. ``version`` is an account-global counter, so
    adjacent version numbers imply no relationship between schemas.
    """

    id: str
    type: str
    groupId: Optional[str]
    version: Optional[int]


class CustomerSchema(TypedDict, total=False):
    """A full customer schema document, including ``content``."""

    id: str
    name: Optional[str]
    type: str
    groupId: Optional[str]
    version: Optional[int]
    content: Dict[str, Any]


class GroupPostProcessRules(TypedDict, total=False):
    """The group post-process-rules envelope.

    Note the asymmetry: the read envelope carries ``version``, while the update
    payload wants ``expectedVersion``. Echoing this envelope straight back into
    the update returns HTTP 409 forever, because ``expectedVersion`` is absent
    and defaults to 0. That is not a race and re-reading will never fix it.
    :meth:`scrapewise.ScrapewiseClient.update_group_post_process_rules` builds
    the correct payload for you.
    """

    groupId: str
    rules: List[PostProcessRule]
    scraperValues: Dict[str, Any]
    version: int
    updated: Optional[str]
    updatedBy: Optional[str]
    counts: Optional[Dict[str, Any]]
    scrapers: Optional[List[Dict[str, Any]]]
    page: Optional[int]
    size: Optional[int]
    totalScrapers: Optional[int]


class PreviewRuleResult(TypedDict, total=False):
    """Result of previewing a single post-process rule against one value.

    ``error`` and ``skipped`` mean different things and both arrive with HTTP
    200. ``error`` means the rule itself is malformed -- fix the ``params``
    keys. ``skipped`` means the rule is valid but declined this input value.
    A wrong ``params`` key yields ``{"output": null, "error": ...}``, which
    reads like a bad value rather than a bad request.
    """

    output: Optional[Any]
    error: Optional[str]
    skipped: Optional[str]


class Desktop(TypedDict, total=False):
    """A desktop (a saved arrangement of groups)."""

    id: str
    name: str
    order: int


__all__ = [
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
    "SiteLink",
]
