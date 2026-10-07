"""Construction, credential resolution, timeouts and lifecycle."""

from __future__ import annotations

import httpx
import pytest
import respx

import scrapewise
from scrapewise import (
    API_KEY_ENV_VAR,
    BASE_URL_ENV_VAR,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    LOAD_SITE_TIMEOUT,
    ScrapewiseClient,
    ScrapewiseConfigurationError,
)


def test_version_is_exported() -> None:
    assert scrapewise.__version__ == "0.1.0"


def test_default_base_url_points_at_the_documented_api_root() -> None:
    assert DEFAULT_BASE_URL == "https://portal.scrapewise.ai/api/scraper-api/api"


def test_default_timeout_matches_the_hosted_mcp_ceiling() -> None:
    assert DEFAULT_TIMEOUT == 60.0
    assert LOAD_SITE_TIMEOUT > DEFAULT_TIMEOUT


def test_missing_api_key_fails_at_construction_not_at_first_call() -> None:
    with pytest.raises(ScrapewiseConfigurationError) as excinfo:
        ScrapewiseClient()
    assert API_KEY_ENV_VAR in str(excinfo.value)


def test_api_key_falls_back_to_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, "env-key")
    with ScrapewiseClient() as sw:
        assert sw._headers()["Authorization"] == "Bearer env-key"


def test_explicit_api_key_beats_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, "env-key")
    with ScrapewiseClient(api_key="explicit") as sw:
        assert sw._headers()["Authorization"] == "Bearer explicit"


def test_base_url_override_strips_a_trailing_slash() -> None:
    with ScrapewiseClient(api_key="k", base_url="https://example.test/api/") as sw:
        assert sw.base_url == "https://example.test/api"


def test_base_url_falls_back_to_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(BASE_URL_ENV_VAR, "https://staging.test/api")
    with ScrapewiseClient(api_key="k") as sw:
        assert sw.base_url == "https://staging.test/api"


def test_repr_shows_the_base_url_and_never_the_key() -> None:
    with ScrapewiseClient(api_key="super-secret") as sw:
        assert "super-secret" not in repr(sw)
        assert DEFAULT_BASE_URL in repr(sw)


def test_an_injected_client_is_not_closed_by_this_client() -> None:
    external = httpx.Client()
    sw = ScrapewiseClient(api_key="k", client=external)
    sw.close()
    assert external.is_closed is False
    external.close()


def test_an_owned_client_is_closed_on_context_exit() -> None:
    sw = ScrapewiseClient(api_key="k")
    with sw:
        pass
    assert sw._client.is_closed is True


@respx.mock
def test_every_request_carries_the_bearer_header(
    client: ScrapewiseClient,
) -> None:
    route = respx.get(f"{DEFAULT_BASE_URL}/scraper/list").mock(
        return_value=httpx.Response(200, json=[])
    )
    client.list_scrapers()
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer YOUR_SCRAPEWISE_API_KEY"
    assert sent.headers["accept"] == "application/json"
    assert "x-api-key" not in sent.headers


@respx.mock
def test_none_valued_query_params_are_dropped(client: ScrapewiseClient) -> None:
    route = respx.get(
        f"{DEFAULT_BASE_URL}/scraper/abc/get-sample-data"
    ).mock(return_value=httpx.Response(200, json=[]))
    client.get_sample_data("abc")
    assert route.calls.last.request.url.params == httpx.QueryParams()


@respx.mock
def test_a_204_response_decodes_to_an_empty_dict(client: ScrapewiseClient) -> None:
    respx.put(f"{DEFAULT_BASE_URL}/scraper").mock(
        return_value=httpx.Response(204)
    )
    assert client.upsert_scraper({"id": "abc"}) == {}
