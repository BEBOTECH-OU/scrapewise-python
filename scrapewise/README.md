# scrapewise

Python client for the [ScrapeWise](https://scrapewise.ai) web-scraping and
price-monitoring API. One runtime dependency (`httpx`), fully type-hinted,
synchronous.

## Install

```bash
pip install scrapewise
```

## Quickstart

```python
from scrapewise import ScrapewiseClient

with ScrapewiseClient(api_key="YOUR_SCRAPEWISE_API_KEY") as sw:   # or env SCRAPEWISE_API_KEY
    groups = sw.list_groups()                                      # GET /scraper/group/list
    rows = sw.get_sample_data(sw.list_scrapers()[0]["id"])          # GET /scraper/{id}/get-sample-data
    print(len(groups), len(rows))
```

## Authentication

**Where to get a key:** sign in at [portal.scrapewise.ai](https://portal.scrapewise.ai)
and create one under **Settings → API Keys**. Two scopes exist:

| Scope | What it can do |
|---|---|
| `LLM_READ` | Lists your groups, reads saved rows and job results. Cannot create, run or delete anything. |
| `LLM_FULL` | The above, plus creating and running scrapers. |

Your sign-in password is not a key, and a key created anywhere else is rejected
with `401`. If reads work but creating or running a scraper returns `401`, the
key is `LLM_READ` and you need an `LLM_FULL` one.

Pass `api_key=` explicitly, or set `SCRAPEWISE_API_KEY` in the environment and
construct with no arguments. The key is sent as `Authorization: Bearer <key>`.
A missing key raises `ScrapewiseConfigurationError` at construction time
instead of failing later with a 401.

```python
import os
os.environ["SCRAPEWISE_API_KEY"] = "YOUR_SCRAPEWISE_API_KEY"
sw = ScrapewiseClient()
```

Self-hosted or staging deployments: pass `base_url=` or set
`SCRAPEWISE_BASE_URL`. The default is
`https://portal.scrapewise.ai/api/scraper-api/api`.

## Timeouts

The default timeout is **60 seconds**, chosen to match the hard tool-call
ceiling of the hosted ScrapeWise MCP gateway so that code written against this
client behaves identically when driven from an agent. The REST API itself has
no such ceiling, so you can raise it:

```python
sw = ScrapewiseClient(timeout=180.0)           # client-wide
sw.get_sample_data(scraper_id, timeout=120.0)  # per call
```

One route is slow by nature: `load_site()` renders a live page and routinely
exceeds 60 s, so it defaults to its own 180 s timeout
(`scrapewise.LOAD_SITE_TIMEOUT`) rather than the client default.

## What is wrapped

Every method maps to exactly one documented REST route. Nothing is inferred.

| Method | Route |
| --- | --- |
| `list_scrapers()` | `GET /scraper/list` |
| `get_scraper(id)` | `GET /scraper/{id}` |
| `upsert_scraper(payload)` | `PUT /scraper` |
| `run_scraper(id)` | `GET /scraper/{id}/run` |
| `get_sample_data(id)` | `GET /scraper/{id}/get-sample-data` |
| `attach_schema(id, schema_id)` | `PATCH /scraper/{id}/schema` |
| `get_scraper_site(id)` | `GET /scraper/{id}/site` |
| `list_site_links(site_id)` | `GET /scraper/site/{siteId}/links` |
| `replace_site_links(...)` | `PUT /scraper/site` |
| `load_site(url)` | `GET /scraper/load-site?url=` |
| `list_groups()` | `GET /scraper/group/list` |
| `upsert_group(payload)` | `PUT /scraper/group` |
| `set_group_currency(id, ccy)` | `PUT /scraper/group/{id}/currency` |
| `get_group_data(id)` | `GET /scraper/data/group/{id}` |
| `get_group_post_process_rules(id)` | `GET /scraper/group/{id}/post-process-rules` |
| `update_group_post_process_rules(...)` | `PUT /scraper/group/{id}/post-process-rules` |
| `get_load_history(scraper_id)` | `GET /scraper/load-history?scraperId=` |
| `get_job_errors(group_id, job_id)` | `GET /scraper/load-history/group/{groupId}/job/{jobId}/errors` |
| `preview_rule(rule, sample_value)` | `POST /scraper/preview-rule` |
| `list_customer_schemas()` | `GET /schema/customer` |
| `get_schema(schema_id)` | `GET /schema/get/{id}` |
| `publish_customer_schema(payload)` | `PUT /schema/customer` |
| `list_desktops()` | `GET /scraper/desktop` |

Two helpers are built on top of those routes and add no new ones:
`iter_group_data()` pages through `get_group_data()`, and `latest_run()`
returns the newest `get_load_history()` entry.

## Errors

All failures raise a subclass of `ScrapewiseError`, which carries `status_code`,
the raw `body`, the request `method`/`url`, and a `payload` property that parses
the body as JSON when possible.

```python
from scrapewise import ScrapewiseAuthError, ScrapewiseError

try:
    sw.list_scrapers()
except ScrapewiseAuthError as exc:
    print("bad key:", exc.status_code)
except ScrapewiseError as exc:
    print(exc.status_code, exc.payload)
```

`400 → ScrapewiseBadRequestError`, `401/403 → ScrapewiseAuthError`,
`404 → ScrapewiseNotFoundError`, `409 → ScrapewiseConflictError`,
`429 → ScrapewiseRateLimitError`, `5xx → ScrapewiseServerError`.
Network failures raise `ScrapewiseTransportError`, timeouts the
`ScrapewiseTimeoutError` subclass.

## Platform behaviour worth knowing

These are properties of the ScrapeWise API, not of this client, and are
repeated in the relevant docstrings:

- `get_sample_data()` returns **at most 100 rows**. It is a sample, not an
  export — use `latest_run()["itemsQuantity"]` for the real row count of a run.
- Paginated responses key rows on `content`, not `items`.
- `replace_site_links()` **replaces** the whole link list for a site. Links not
  present in the call are removed.
- `attach_schema()` is effectively one-way: it switches the scraper's extractor
  to the AI/schema path.
- Writing group post-process rules is optimistically locked. Read returns
  `version`; the write expects `expectedVersion`.
  `update_group_post_process_rules()` does that rename for you.
- A scraper is scoped to one domain. Posting links from another host fails with
  `LINK_HOST_MISMATCH`.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest
```

Tests mock HTTP at the transport layer with `respx`; there are no live network
calls in the suite.

## License

MIT © BEBOTECH OÜ
