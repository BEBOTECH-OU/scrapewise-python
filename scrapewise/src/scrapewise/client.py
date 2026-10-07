"""Synchronous REST client for the Scrapewise platform API.

Only routes that have been verified against the live platform are exposed. The
docstring of every method names the HTTP route it calls, so a reader can map a
method back onto the API without guessing.
"""

from __future__ import annotations

import json as _json
import os
from types import TracebackType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Type

import httpx

from .errors import (
    ScrapewiseConfigurationError,
    ScrapewiseError,
    ScrapewiseTimeoutError,
    ScrapewiseTransportError,
    error_for_status,
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
    ScraperGroup,
    ScraperSite,
    SiteLink,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "LOAD_SITE_TIMEOUT",
    "ScrapewiseClient",
]

#: Production REST base. Every route below is relative to this.
DEFAULT_BASE_URL = "https://portal.scrapewise.ai/api/scraper-api/api"

#: Default per-request timeout, in seconds.
#:
#: 60 s is chosen to match the hard ceiling of the hosted MCP gateway at
#: ``https://mcp.scrapewise.ai/mcp``, so code written against this client
#: behaves the same whether it is driven directly or through an MCP tool call.
#: The REST API itself imposes no such ceiling -- raise this freely for the
#: slow routes. ``load_site`` already overrides it (see ``LOAD_SITE_TIMEOUT``).
DEFAULT_TIMEOUT = 60.0

#: Default timeout for :meth:`ScrapewiseClient.load_site`.
#:
#: That route fetches a page through the platform's own proxy and routinely
#: takes longer than 60 s on a large catalogue page. A 60 s budget there
#: produces a client-side timeout that is easy to misread as a dead route.
LOAD_SITE_TIMEOUT = 180.0

#: Environment variable consulted when no ``api_key`` is passed.
API_KEY_ENV_VAR = "SCRAPEWISE_API_KEY"

#: Environment variable consulted when no ``base_url`` is passed.
BASE_URL_ENV_VAR = "SCRAPEWISE_BASE_URL"


class ScrapewiseClient:
    """A thin synchronous client for the Scrapewise REST API.

    Args:
        api_key: Your API key from the portal (Settings > API Keys). When
            omitted, the ``SCRAPEWISE_API_KEY`` environment variable is used.
            Raises :class:`~scrapewise.ScrapewiseConfigurationError` if neither
            is available.
        base_url: Override the API root. Defaults to the
            ``SCRAPEWISE_BASE_URL`` environment variable, then to
            :data:`DEFAULT_BASE_URL`.
        timeout: Default per-request timeout in seconds. Defaults to
            :data:`DEFAULT_TIMEOUT` (60 s). Every method also accepts a
            per-call ``timeout`` that overrides this.
        transport: An ``httpx`` transport, for tests or for custom retry and
            proxy behaviour.
        client: Supply a pre-built ``httpx.Client`` to take full control of
            connection pooling, proxies and retries. Its ``base_url`` and
            headers are ignored; this class always sets them per request.

    The client is safe to reuse across many calls and holds one pooled HTTP
    connection. It is **not** thread-safe beyond what ``httpx.Client`` itself
    guarantees. Use it as a context manager, or call :meth:`close`.

    Example:
        >>> from scrapewise import ScrapewiseClient
        >>> with ScrapewiseClient(api_key="YOUR_SCRAPEWISE_API_KEY") as sw:
        ...     scrapers = sw.list_scrapers()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport: Optional[httpx.BaseTransport] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        resolved_key = api_key or os.environ.get(API_KEY_ENV_VAR)
        if not resolved_key:
            raise ScrapewiseConfigurationError(
                "No Scrapewise API key. Pass api_key=... or set the "
                f"{API_KEY_ENV_VAR} environment variable. Create a key in the "
                "portal under Settings > API Keys."
            )
        self._api_key = resolved_key
        self._base_url = (
            base_url or os.environ.get(BASE_URL_ENV_VAR) or DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.Client(transport=transport, timeout=timeout)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        """The API root this client talks to, without a trailing slash."""
        return self._base_url

    def close(self) -> None:
        """Close the underlying HTTP connection pool.

        A no-op when an externally supplied ``httpx.Client`` is in use -- the
        caller owns that one.
        """
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "ScrapewiseClient":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"ScrapewiseClient(base_url={self._base_url!r})"

    # ------------------------------------------------------------------
    # transport
    # ------------------------------------------------------------------

    def _headers(self, extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
        as_text: bool = False,
    ) -> Any:
        """Issue one request and return the decoded body.

        Raises:
            ScrapewiseTimeoutError: the request exceeded its timeout.
            ScrapewiseTransportError: no response arrived.
            ScrapewiseAPIError: a non-2xx response arrived. The concrete
                subclass depends on the status; the server's body is on
                ``.body`` and, when it was JSON, on ``.payload``.
        """
        url = f"{self._base_url}/{path.lstrip('/')}"
        cleaned = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            response = self._client.request(
                method,
                url,
                params=cleaned or None,
                json=json_body,
                headers=self._headers(headers),
                timeout=self.timeout if timeout is None else timeout,
            )
        except httpx.TimeoutException as exc:
            raise ScrapewiseTimeoutError(
                f"Request timed out after "
                f"{self.timeout if timeout is None else timeout}s",
                method=method,
                url=url,
            ) from exc
        except httpx.HTTPError as exc:
            raise ScrapewiseTransportError(
                f"Could not reach the Scrapewise API: {exc}",
                method=method,
                url=url,
            ) from exc

        if response.status_code >= 400:
            raise error_for_status(
                response.status_code,
                body=response.text,
                method=method,
                url=url,
            )

        if as_text:
            return response.text
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ScrapewiseError(
                "Expected a JSON response body but could not decode one",
                status_code=response.status_code,
                body=response.text,
                method=method,
                url=url,
            ) from exc

    # ------------------------------------------------------------------
    # scrapers
    # ------------------------------------------------------------------

    def list_scrapers(self, *, timeout: Optional[float] = None) -> List[Scraper]:
        """List every scraper on the account.

        Route: ``GET /scraper/list``

        Warning:
            This projection **omits** ``schemaId`` -- it reads as ``None`` for
            every scraper, including ones that are bound. Never use this route
            to answer "is anything bound to this schema"; fan out over
            :meth:`get_scraper` instead.
        """
        result = self._request("GET", "/scraper/list", timeout=timeout)
        return result if isinstance(result, list) else result.get("content", [])

    def get_scraper(
        self, scraper_id: str, *, timeout: Optional[float] = None
    ) -> Scraper:
        """Fetch one scraper's full DTO.

        Route: ``GET /scraper/{scraper_id}``

        Note:
            Most configuration is nested under ``config``: ``itemsConfig``,
            ``postProcessRules``, ``sourceConfig``, ``startType``, ``timeout``.
            Only ``mapping``, ``type``, ``manual``, ``siteMap``, ``lastRun``,
            ``lastRunState``, ``groupId`` and ``schemaId`` are top level.
        """
        return self._request("GET", f"/scraper/{scraper_id}", timeout=timeout)

    def upsert_scraper(
        self, scraper: Mapping[str, Any], *, timeout: Optional[float] = None
    ) -> Scraper:
        """Create or update a scraper and return the stored DTO.

        Route: ``PUT /scraper``

        Pass a DTO with an ``id`` to update, or without one to create -- the
        response carries the newly minted id.

        Warning:
            Two server-side behaviours surprise people here. First, when the
            scraper has a ``schemaId``, any ``config.itemsConfig`` you send is
            **ignored** and re-derived from the schema; send
            ``itemsConfig: []`` to force a refresh after a schema change.
            ``config.postProcessRules`` do persist. Second, ``schemaId: null``
            on an already-bound scraper returns HTTP 200 and is silently
            ignored -- there is no unbind.
        """
        return self._request("PUT", "/scraper", json_body=dict(scraper), timeout=timeout)

    def run_scraper(self, scraper_id: str, *, timeout: Optional[float] = None) -> Any:
        """Start a run of one scraper.

        Route: ``GET /scraper/{scraper_id}/run``

        Raises:
            ScrapewiseBadRequestError: with the message "Scraper is disabled or
                already in RUNNING or PENDING state". That one message covers
                three unrelated causes, including a scraper that is not
                runnable at all (a CSS scraper needs a non-empty
                ``sourceConfig.url`` *and* either a non-empty ``mapping`` or a
                bound schema). Check the DTO before assuming a stuck job.
        """
        return self._request("GET", f"/scraper/{scraper_id}/run", timeout=timeout)

    def get_sample_data(
        self,
        scraper_id: str,
        *,
        prefer_persisted: Optional[bool] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Fetch sample extracted rows for one scraper.

        Route: ``GET /scraper/{scraper_id}/get-sample-data``

        Args:
            prefer_persisted: When true, serve rows already persisted from the
                previous run instead of re-extracting.

        Warning:
            The response is **capped at 100 rows**, so it can never be used to
            count what a scraper stored -- read ``itemsQuantity`` from
            :meth:`get_load_history` for that. If several unrelated scrapers
            all report exactly 100, that is the cap, not the data.

            With ``prefer_persisted=True`` the rows describe the *previous*
            run, which looks indistinguishable from a successful new one. Check
            ``lastRunState`` on the scraper before reading these as evidence
            about a run you just triggered.
        """
        return self._request(
            "GET",
            f"/scraper/{scraper_id}/get-sample-data",
            params={"preferPersisted": prefer_persisted},
            timeout=timeout,
        )

    def attach_schema(
        self, scraper_id: str, schema_id: str, *, timeout: Optional[float] = None
    ) -> Scraper:
        """Bind a scraper to one immutable schema version.

        Route: ``PATCH /scraper/{scraper_id}/schema``

        Warning:
            **This is a one-way door.** No unbind exists: every form of
            ``{"schemaId": null}`` is rejected or silently ignored, and the
            only way back to an unbound scraper is to create a new one.

            Binding does not merely filter which columns are stored -- it
            overrides ``manual: true`` and switches the scraper to AI
            extraction, so a CSS ``mapping`` stops being honoured and the
            extracted *values* change. If you want CSS selectors respected,
            the scraper must keep ``schemaId: None``.

            ``schema_id`` must be a concrete version id, not a schema version
            *family* id (the hyphenated UUID on a schema's ``groupId``).
            Publishing a new version onto a family does not repoint anything;
            every bound scraper needs re-attaching by hand.
        """
        return self._request(
            "PATCH",
            f"/scraper/{scraper_id}/schema",
            json_body={"schemaId": schema_id},
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # sites and links
    # ------------------------------------------------------------------

    def get_scraper_site(
        self, scraper_id: str, *, timeout: Optional[float] = None
    ) -> ScraperSite:
        """Fetch the site document attached to a scraper.

        Route: ``GET /scraper/{scraper_id}/site``

        Note:
            ``links`` comes back as ``None`` here even on a site with links;
            only ``id`` and ``linkCount`` are populated. Pass the returned
            ``id`` -- the *site* id -- to :meth:`list_site_links`.
        """
        return self._request("GET", f"/scraper/{scraper_id}/site", timeout=timeout)

    def list_site_links(
        self,
        site_id: str,
        *,
        page: int = 0,
        size: int = 200,
        sort_field: str = "url",
        sort_direction: str = "asc",
        timeout: Optional[float] = None,
    ) -> Page:
        """List a site's links, paginated.

        Route: ``GET /scraper/site/{site_id}/links``

        Args:
            site_id: The **site** document id, from
                :meth:`get_scraper_site`. Passing a scraper id here returns
                HTTP 400 "Site <id> not found", which looks like a missing site
                rather than a wrong id.

        Returns:
            A page envelope whose rows are under ``content``, each
            ``{"title": ..., "url": ...}``.

        Note:
            This is the only trustworthy source for a link list. Reconstructing
            one from a previous run's output rows silently produces a different
            list.
        """
        return self._request(
            "GET",
            f"/scraper/site/{site_id}/links",
            params={
                "page": page,
                "size": size,
                "sortField": sort_field,
                "sortDirection": sort_direction,
            },
            timeout=timeout,
        )

    def replace_site_links(
        self,
        scraper_id: str,
        links: Sequence[SiteLink],
        *,
        site_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ScraperSite:
        """Replace a site's entire link list.

        Route: ``PUT /scraper/site``

        Warning:
            **This overwrites the whole set; it does not append.** There is no
            add-links endpoint. To add one link you must send every existing
            link plus the new one -- read them first with
            :meth:`list_site_links`. Sending a single link to a 12-link site
            leaves it with 1 link.

            Omitting ``site_id`` mints a **new** site document and orphans the
            old one. Call :meth:`get_scraper_site` first and reuse its ``id``
            unless you genuinely want a fresh site.

        Raises:
            ScrapewiseBadRequestError: ``LINK_HOST_MISMATCH`` when any link's
                host differs from ``sourceConfig.url``'s host (a leading
                ``www.`` is normalised away). One scraper serves one domain.
        """
        body: Dict[str, Any] = {
            "scraperId": scraper_id,
            "links": [dict(link) for link in links],
        }
        if site_id is not None:
            body["id"] = site_id
        return self._request("PUT", "/scraper/site", json_body=body, timeout=timeout)

    def load_site(
        self, url: str, *, timeout: float = LOAD_SITE_TIMEOUT
    ) -> str:
        """Fetch a page's raw HTML through the platform's own proxy.

        Route: ``GET /scraper/load-site?url=<url>``

        Use this to settle "can the platform see this page?" independently of
        your own IP, and to check for JavaScript-injected JSON-LD.

        Args:
            timeout: Defaults to :data:`LOAD_SITE_TIMEOUT` (180 s) because this
                route regularly exceeds 60 s and returns bodies approaching a
                megabyte. A timeout here is a budget problem, not a dead route.

        Returns:
            The page HTML as text. Unlike every other method on this client
            this is not JSON.
        """
        return self._request(
            "GET",
            "/scraper/load-site",
            params={"url": url},
            headers={"Accept": "text/html, */*"},
            timeout=timeout,
            as_text=True,
        )

    # ------------------------------------------------------------------
    # groups
    # ------------------------------------------------------------------

    def list_groups(self, *, timeout: Optional[float] = None) -> List[ScraperGroup]:
        """List every scraper group on the account.

        Route: ``GET /scraper/group/list``
        """
        result = self._request("GET", "/scraper/group/list", timeout=timeout)
        return result if isinstance(result, list) else result.get("content", [])

    def upsert_group(
        self, group: Mapping[str, Any], *, timeout: Optional[float] = None
    ) -> ScraperGroup:
        """Create or update a scraper group.

        Route: ``PUT /scraper/group``
        """
        return self._request(
            "PUT", "/scraper/group", json_body=dict(group), timeout=timeout
        )

    def set_group_currency(
        self,
        group_id: str,
        currency: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Set a group's display currency.

        Route: ``PUT /scraper/group/{group_id}/currency``

        Args:
            idempotency_key: Sent as the ``Idempotency-Key`` header. This route
                honours it; most do not.

        Note:
            The portal converts at read time against live rates and disables
            conversion for any source whose rows carry more than one distinct
            currency, so prefer a scraped per-row ``currency`` column over a
            hardcoded ``CURRENCY_CONVERT`` rule with a fixed ``from``.
        """
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._request(
            "PUT",
            f"/scraper/group/{group_id}/currency",
            json_body={"currency": currency},
            headers=headers,
            timeout=timeout,
        )

    def get_group_data(
        self,
        group_id: str,
        *,
        page: int = 0,
        size: int = 100,
        timeout: Optional[float] = None,
    ) -> Page:
        """Fetch extracted rows for a whole group, paginated.

        Route: ``GET /scraper/data/group/{group_id}``

        Returns:
            A page envelope whose rows are under ``content``, **not**
            ``items``.

        Note:
            Stored column names are not schema field names. A schema may
            declare ``list`` / ``sale`` / ``gtin`` while the rows carry
            ``list_price`` / ``sale_price`` / ``regularPrice``. Dump one real
            row before computing any coverage or quality metric off field
            names, or you will measure a fake 100% empty.

            Rows also carry platform-injected columns: ``title``, ``url``,
            ``_sw_scraper``, ``_sw_group``, ``_sw_run_date``, ``_sw_run_time``.
        """
        return self._request(
            "GET",
            f"/scraper/data/group/{group_id}",
            params={"page": page, "size": size},
            timeout=timeout,
        )

    def get_group_post_process_rules(
        self, group_id: str, *, timeout: Optional[float] = None
    ) -> GroupPostProcessRules:
        """Read a group's post-process rules, with the concurrency version.

        Route: ``GET /scraper/group/{group_id}/post-process-rules``

        Note:
            ``counts.undeclaredInputs`` per scraper is the quickest check that
            a rule's input column actually exists on that scraper.
        """
        return self._request(
            "GET", f"/scraper/group/{group_id}/post-process-rules", timeout=timeout
        )

    def update_group_post_process_rules(
        self,
        group_id: str,
        *,
        rules: Sequence[PostProcessRule],
        scraper_values: Mapping[str, Any],
        expected_version: int,
        timeout: Optional[float] = None,
    ) -> Any:
        """Replace a group's post-process rules.

        Route: ``PUT /scraper/group/{group_id}/post-process-rules``

        Args:
            expected_version: The ``version`` from
                :meth:`get_group_post_process_rules`. The read envelope calls
                it ``version`` and the write payload calls it
                ``expectedVersion``; this method does that rename for you.

        Raises:
            ScrapewiseConflictError: HTTP 409 "Someone else saved first".
                Genuine when your ``expected_version`` is stale. Note that
                echoing the read envelope back verbatim -- i.e. sending
                ``version`` and no ``expectedVersion`` -- produces this error
                *forever*, because the missing field defaults to 0. That is not
                a race and re-reading will never clear it.
        """
        body = {
            "rules": [dict(rule) for rule in rules],
            "scraperValues": dict(scraper_values),
            "expectedVersion": expected_version,
        }
        return self._request(
            "PUT",
            f"/scraper/group/{group_id}/post-process-rules",
            json_body=body,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # runs
    # ------------------------------------------------------------------

    def get_load_history(
        self,
        scraper_id: str,
        *,
        page: int = 0,
        size: int = 1,
        timeout: Optional[float] = None,
    ) -> Page:
        """Fetch run history for one scraper, newest first.

        Route: ``GET /scraper/load-history?scraperId=...``

        Returns:
            A page envelope whose rows are under ``content``. Each entry
            carries ``itemsQuantity`` (the authoritative row count for that
            run), ``totalRequests``, ``attempted``, ``notAttempted``,
            ``state``, ``duration``, ``stopReason``, ``errorMessage`` and
            ``costLines``.

        Note:
            An empty ``errorMessage`` with an empty ``stopReason`` is not
            evidence of health. Several failure modes -- a top-level ``type``
            that does not match the configuration, or a ``url`` field that
            resolves to null and collapses every page into one deduplicated
            row -- report nothing at all. Compare ``itemsQuantity`` against
            ``attempted``.
        """
        return self._request(
            "GET",
            "/scraper/load-history",
            params={"scraperId": scraper_id, "page": page, "size": size},
            timeout=timeout,
        )

    def get_job_errors(
        self, group_id: str, job_id: str, *, timeout: Optional[float] = None
    ) -> Any:
        """Fetch per-page errors for one job of one group.

        Route: ``GET /scraper/load-history/group/{group_id}/job/{job_id}/errors``
        """
        return self._request(
            "GET",
            f"/scraper/load-history/group/{group_id}/job/{job_id}/errors",
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # post-process rule preview
    # ------------------------------------------------------------------

    def preview_rule(
        self,
        rule: Mapping[str, Any],
        sample_value: Any,
        *,
        timeout: Optional[float] = None,
    ) -> PreviewRuleResult:
        """Dry-run one post-process rule against one value.

        Route: ``POST /scraper/preview-rule``

        Args:
            rule: ``{kind, sourceField, outputField, outputType, params}``.
                ``kind`` is one of ``CURRENCY_CONVERT``, ``ENUM_MAP``,
                ``REGEX_CLEAN``, ``QUANTITY_NORMALIZE``, ``NUMBER_EXTRACT``.
            sample_value: The input value to run the rule against.

        Returns:
            ``{"output": ..., "error": ..., "skipped": ...}``.

        Note:
            ``error`` and ``skipped`` are different fields and both arrive with
            HTTP 200. ``error`` means the rule is malformed -- most often a
            ``params`` key that does not exist, which returns
            ``{"output": null, "error": "Rule execution failed"}`` and reads
            like a bad value. ``skipped`` means the rule is valid but declined
            this input. Read which one came back before theorising.
        """
        return self._request(
            "POST",
            "/scraper/preview-rule",
            json_body={"rule": dict(rule), "sampleValue": sample_value},
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # schemas
    # ------------------------------------------------------------------

    def list_customer_schemas(
        self, *, timeout: Optional[float] = None
    ) -> List[CustomerSchemaSummary]:
        """List the account's custom schemas.

        Route: ``GET /schema/customer``

        Note:
            Metadata only -- no ``content`` and no ``name``. Use
            :meth:`get_schema` to see what a schema declares. Reading a
            scraper's cached ``config.itemsConfig`` instead is not a
            substitute; it can be stale after a schema version bump.
        """
        result = self._request("GET", "/schema/customer", timeout=timeout)
        return result if isinstance(result, list) else result.get("content", [])

    def get_schema(
        self, schema_id: str, *, timeout: Optional[float] = None
    ) -> CustomerSchema:
        """Fetch one schema document in full, including ``content``.

        Route: ``GET /schema/get/{schema_id}``

        This is the authority on what a schema declares.
        """
        return self._request("GET", f"/schema/get/{schema_id}", timeout=timeout)

    def publish_customer_schema(
        self, schema: Mapping[str, Any], *, timeout: Optional[float] = None
    ) -> CustomerSchema:
        """Publish a custom schema version.

        Route: ``PUT /schema/customer``

        Custom schemas are immutable and versioned: reusing a schema's
        ``groupId`` (the hyphenated-UUID version family) appends a version
        rather than editing one.

        Note:
            Publishing does **not** repoint any scraper. A scraper binds to one
            concrete version id via :meth:`attach_schema`, so shipping a schema
            fix leaves every bound scraper on the old columns until you
            re-attach each of them. ``version`` is an account-global counter,
            so a version number adjacent to another schema's implies no
            relationship.

            Field design matters more than wording: a field listed in
            ``content.properties.<array>.items.required`` is always emitted and
            always filled, which fabricates values for fields that should
            usually be empty, while descriptions, ``enum`` constraints and
            boolean types are all treated as prose and do not bind. Copy a
            schema that already works in production rather than hand-rolling
            constraints.
        """
        return self._request(
            "PUT", "/schema/customer", json_body=dict(schema), timeout=timeout
        )

    # ------------------------------------------------------------------
    # desktops
    # ------------------------------------------------------------------

    def list_desktops(self, *, timeout: Optional[float] = None) -> List[Desktop]:
        """List the account's desktops.

        Route: ``GET /scraper/desktop``

        Returns:
            ``[{"id": ..., "name": ..., "order": ...}, ...]``
        """
        result = self._request("GET", "/scraper/desktop", timeout=timeout)
        return result if isinstance(result, list) else result.get("content", [])

    # ------------------------------------------------------------------
    # convenience
    # ------------------------------------------------------------------

    def iter_group_data(
        self,
        group_id: str,
        *,
        size: int = 100,
        max_pages: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> List[DataRow]:
        """Read every page of a group's data and return the rows concatenated.

        Thin loop over :meth:`get_group_data`. Stops when a page returns fewer
        than ``size`` rows, when ``content`` is empty, or after ``max_pages``.

        Args:
            max_pages: Hard stop, so a mis-set ``size`` cannot turn into an
                unbounded crawl. ``None`` means no limit.
        """
        rows: List[DataRow] = []
        page = 0
        while True:
            if max_pages is not None and page >= max_pages:
                break
            payload = self.get_group_data(
                group_id, page=page, size=size, timeout=timeout
            )
            batch = payload.get("content") or []
            rows.extend(batch)
            if len(batch) < size:
                break
            page += 1
        return rows

    def latest_run(
        self, scraper_id: str, *, timeout: Optional[float] = None
    ) -> Optional[LoadHistoryEntry]:
        """Return the most recent run of a scraper, or ``None`` if it never ran.

        Thin wrapper over :meth:`get_load_history` with ``size=1``.
        """
        payload = self.get_load_history(scraper_id, page=0, size=1, timeout=timeout)
        content = payload.get("content") or []
        return content[0] if content else None

    def to_json(self, value: Any, *, indent: Optional[int] = 2) -> str:
        """Serialise an API payload back to JSON text.

        Convenience for callers that hand platform payloads to an LLM or a log.
        """
        return _json.dumps(value, indent=indent, ensure_ascii=False, default=str)
