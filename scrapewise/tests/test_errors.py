"""Status-to-exception mapping and error payload surfacing."""

from __future__ import annotations

import httpx
import pytest
import respx

from scrapewise import (
    DEFAULT_BASE_URL,
    ScrapewiseAPIError,
    ScrapewiseAuthError,
    ScrapewiseBadRequestError,
    ScrapewiseClient,
    ScrapewiseConflictError,
    ScrapewiseError,
    ScrapewiseNotFoundError,
    ScrapewiseRateLimitError,
    ScrapewiseServerError,
    ScrapewiseTimeoutError,
    ScrapewiseTransportError,
)

BASE = DEFAULT_BASE_URL


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, ScrapewiseBadRequestError),
        (401, ScrapewiseAuthError),
        (403, ScrapewiseAuthError),
        (404, ScrapewiseNotFoundError),
        (409, ScrapewiseConflictError),
        (429, ScrapewiseRateLimitError),
        (500, ScrapewiseServerError),
        (502, ScrapewiseServerError),
    ],
)
@respx.mock
def test_status_codes_map_to_specific_exceptions(
    client: ScrapewiseClient, status: int, expected: type
) -> None:
    respx.get(f"{BASE}/scraper/list").mock(
        return_value=httpx.Response(status, json={"message": "nope"})
    )
    with pytest.raises(expected) as excinfo:
        client.list_scrapers()
    assert excinfo.value.status_code == status
    assert isinstance(excinfo.value, ScrapewiseAPIError)
    assert isinstance(excinfo.value, ScrapewiseError)


@respx.mock
def test_the_server_error_body_is_preserved_and_parsed(
    client: ScrapewiseClient,
) -> None:
    respx.put(f"{BASE}/scraper/site").mock(
        return_value=httpx.Response(400, json={"code": "LINK_HOST_MISMATCH"})
    )
    with pytest.raises(ScrapewiseBadRequestError) as excinfo:
        client.replace_site_links("65f1", [{"url": "https://other.test/p"}])
    error = excinfo.value
    assert error.payload == {"code": "LINK_HOST_MISMATCH"}
    assert "LINK_HOST_MISMATCH" in error.body
    assert error.method == "PUT"
    assert error.url.endswith("/scraper/site")


@respx.mock
def test_a_non_json_error_body_leaves_payload_none(
    client: ScrapewiseClient,
) -> None:
    respx.get(f"{BASE}/scraper/list").mock(
        return_value=httpx.Response(502, text="<html>Bad Gateway</html>")
    )
    with pytest.raises(ScrapewiseServerError) as excinfo:
        client.list_scrapers()
    assert excinfo.value.payload is None
    assert "Bad Gateway" in excinfo.value.body


@respx.mock
def test_a_timeout_raises_the_timeout_subclass(client: ScrapewiseClient) -> None:
    respx.get(f"{BASE}/scraper/list").mock(
        side_effect=httpx.ReadTimeout("too slow")
    )
    with pytest.raises(ScrapewiseTimeoutError) as excinfo:
        client.list_scrapers()
    assert isinstance(excinfo.value, ScrapewiseTransportError)


@respx.mock
def test_a_connect_failure_raises_transport_not_api_error(
    client: ScrapewiseClient,
) -> None:
    respx.get(f"{BASE}/scraper/list").mock(
        side_effect=httpx.ConnectError("no route to host")
    )
    with pytest.raises(ScrapewiseTransportError) as excinfo:
        client.list_scrapers()
    assert not isinstance(excinfo.value, ScrapewiseAPIError)
    assert excinfo.value.status_code is None


@respx.mock
def test_a_200_with_an_undecodable_body_raises_scrapewise_error(
    client: ScrapewiseClient,
) -> None:
    respx.get(f"{BASE}/scraper/list").mock(
        return_value=httpx.Response(200, text="not json at all")
    )
    with pytest.raises(ScrapewiseError) as excinfo:
        client.list_scrapers()
    assert excinfo.value.status_code == 200


@respx.mock
def test_str_truncates_a_very_long_body(client: ScrapewiseClient) -> None:
    respx.get(f"{BASE}/scraper/list").mock(
        return_value=httpx.Response(500, text="x" * 5000)
    )
    with pytest.raises(ScrapewiseServerError) as excinfo:
        client.list_scrapers()
    rendered = str(excinfo.value)
    assert len(rendered) < 1000
    assert len(excinfo.value.body) == 5000
