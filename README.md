# ScrapeWise for Python

Official Python packages for [ScrapeWise](https://scrapewise.ai) — competitor
price monitoring and product-data extraction.

| Package | What it is | PyPI |
|---|---|---|
| [`scrapewise`](scrapewise/) | Python client for the ScrapeWise REST API. One runtime dependency (`httpx`), fully type-hinted. | `pip install scrapewise` |
| [`langchain-scrapewise`](langchain-scrapewise/) | Twelve read-only LangChain tools over the same API, for use with any tool-calling model. | `pip install langchain-scrapewise` |

## Getting an API key

Sign in at [portal.scrapewise.ai](https://portal.scrapewise.ai) and create a key
under **Settings → API Keys**. Two scopes exist:

| Scope | What it can do |
|---|---|
| `LLM_READ` | Lists your groups, reads saved rows and job results. Cannot create, run or delete anything. |
| `LLM_FULL` | The above, plus creating and running scrapers. |

`langchain-scrapewise` only ever reads, so `LLM_READ` is enough for it — which
is what you want behind a model. Your sign-in password is not a key.

## Quickstart

```python
from scrapewise import ScrapewiseClient

with ScrapewiseClient() as sw:          # reads SCRAPEWISE_API_KEY from the environment
    for group in sw.list_groups():
        print(group["displayName"])
```

## Also available

ScrapeWise has a hosted MCP server, so agents can use it without any Python at
all: [scrapewise.ai/mcp](https://scrapewise.ai/mcp)
([mirror repo](https://github.com/BEBOTECH-OU/scrapewise-mcp)).

## Development

Each package is independent and installs editable with its test extras:

```bash
cd scrapewise
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest -q
```

`langchain-scrapewise` additionally needs the client from this repo:

```bash
cd langchain-scrapewise
python3 -m venv .venv && .venv/bin/pip install -e ".[test]" && .venv/bin/pip install -e ../scrapewise
.venv/bin/python -m pytest -q
```

## Releasing

Publishing runs on GitHub Actions via PyPI Trusted Publishing — there is no API
token stored anywhere. Push a tag named `<package>-v<version>`:

```bash
git tag scrapewise-v0.1.0 && git push origin scrapewise-v0.1.0
```

The version in the tag must match `version` in that package's `pyproject.toml`;
the workflow fails the release if they disagree, because PyPI will not let a
version be replaced once it is published.

## Licence

MIT — see each package's `LICENSE`.
