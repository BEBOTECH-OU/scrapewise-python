# langchain-scrapewise

LangChain tools for [ScrapeWise](https://scrapewise.ai) — competitor price
monitoring and product-data extraction. Twelve tools over the ScrapeWise REST
API, usable with any tool-calling chat model.

## Install

```bash
pip install langchain-scrapewise
```

## Get an API key

Sign in at [portal.scrapewise.ai](https://portal.scrapewise.ai) and create a key
under **Settings → API Keys**. All twelve tools here are read-only, so an
`LLM_READ` key is enough — it cannot create, run or delete anything, which is
what you want behind a model. Your sign-in password is not a key, and a key
created anywhere else is rejected with `401`.

Pass it as `api_key=`, or set `SCRAPEWISE_API_KEY` in the environment and
construct with no arguments.

## Quickstart

```python
from langchain_scrapewise import ScrapewiseToolkit

tools = ScrapewiseToolkit(api_key="YOUR_SCRAPEWISE_API_KEY").get_tools()
llm_with_tools = llm.bind_tools(tools)   # any tool-calling chat model

response = llm_with_tools.invoke(
    "Which of my ScrapeWise scrapers produced the fewest rows on its last run?"
)
print(response.tool_calls)
```

The toolkit builds one `ScrapewiseClient` and shares it across all twelve
tools, so an agent holding the full set still uses a single connection pool.

### A single tool

```python
from langchain_scrapewise import ScrapewiseGroupDataTool

tool = ScrapewiseGroupDataTool(api_key="YOUR_SCRAPEWISE_API_KEY")
print(tool.invoke({"group_id": "<group id>", "size": 20}))
```

### Sharing a pre-configured client

```python
from langchain_scrapewise import ScrapewiseListScrapersTool, ScrapewiseRunScraperTool
from scrapewise import ScrapewiseClient

client = ScrapewiseClient(api_key="YOUR_SCRAPEWISE_API_KEY", timeout=120.0)
tools = [ScrapewiseListScrapersTool(client=client), ScrapewiseRunScraperTool(client=client)]
```

### Full agent example

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_scrapewise import ScrapewiseToolkit

tools = ScrapewiseToolkit().get_tools()         # reads $SCRAPEWISE_API_KEY
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a pricing analyst. Use the ScrapeWise tools to answer with real data."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])
executor = AgentExecutor(agent=create_tool_calling_agent(llm, tools, prompt), tools=tools)
executor.invoke({"input": "Compare our prices against the DE group and list where we are highest."})
```

## Authentication

Set `SCRAPEWISE_API_KEY` in the environment, or pass `api_key=` to any tool or
to the toolkit. Credentials are resolved lazily — constructing a tool with no
key succeeds, and the `ScrapewiseConfigurationError` only surfaces on first
use. That means you can declare tools in config before secrets are wired up.

`base_url=` / `SCRAPEWISE_BASE_URL` points the tools at a staging or
self-hosted deployment. `timeout=` is per-request, in seconds.

## Tools

| Tool name | Class | What it does |
| --- | --- | --- |
| `scrapewise_list_scrapers` | `ScrapewiseListScrapersTool` | List all scrapers with ids and last-run state |
| `scrapewise_get_scraper` | `ScrapewiseGetScraperTool` | One scraper's full configuration |
| `scrapewise_get_sample_data` | `ScrapewiseSampleDataTool` | Sample extracted product rows (API caps at 100) |
| `scrapewise_run_scraper` | `ScrapewiseRunScraperTool` | Start a scrape run (async) |
| `scrapewise_get_run_history` | `ScrapewiseRunHistoryTool` | Recent runs: rows stored, pages attempted, errors |
| `scrapewise_list_scraper_groups` | `ScrapewiseListGroupsTool` | List scraper groups (one market / competitor set) |
| `scrapewise_get_group_data` | `ScrapewiseGroupDataTool` | Paginated cross-competitor rows for a group |
| `scrapewise_get_scraper_site` | `ScrapewiseGetScraperSiteTool` | A scraper's site id and link count |
| `scrapewise_list_site_links` | `ScrapewiseSiteLinksTool` | The product URLs a site will scrape |
| `scrapewise_get_group_rules` | `ScrapewiseGroupRulesTool` | A group's post-process rules |
| `scrapewise_preview_rule` | `ScrapewisePreviewRuleTool` | Dry-run one post-process rule against one value |
| `scrapewise_list_schemas` | `ScrapewiseListSchemasTool` | List extraction schemas (metadata only) |

Every tool returns JSON **text**, capped at 12,000 characters with an explicit
`... [truncated]` marker (`langchain_scrapewise.base.MAX_CHARS`). Group data and
page HTML are routinely megabytes; truncating mid-document silently would read
to the model as corrupt data rather than as a limit.

### Read-biased on purpose

Eleven of the twelve tools are read-only. The one exception,
`scrapewise_run_scraper`, starts a run and nothing else. Routes that rewrite
configuration — publishing a schema version, replacing a site's link list,
writing group post-process rules, reordering desktops — are deliberately **not**
exposed. They are destructive (`PUT /scraper/site` replaces the whole link list;
attaching a schema is effectively one-way) and belong to a human operator. Use
the [`scrapewise`](https://pypi.org/project/scrapewise/) client directly for
those.

### API errors come back as text

A raised exception inside a tool aborts the whole agent run. These tools catch
`ScrapewiseError` and return it as JSON instead:

```json
{"error": "ScrapewiseNotFoundError", "status": 404, "message": "..."}
```

The model can then correct a bad id or an over-wide page size by itself.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest
```

The suite replaces the client with a recorder, so it needs no API key and makes
no network calls.

## License

MIT © BEBOTECH OÜ
