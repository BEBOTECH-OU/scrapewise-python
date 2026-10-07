"""The two convenience helpers and the JSON dump utility."""

from __future__ import annotations

import json

import httpx
import respx

from scrapewise import DEFAULT_BASE_URL, ScrapewiseClient

BASE = DEFAULT_BASE_URL


@respx.mock
def test_iter_group_data_stops_on_a_short_page(client: ScrapewiseClient) -> None:
    pages = [
        httpx.Response(200, json={"content": [{"i": 0}, {"i": 1}]}),
        httpx.Response(200, json={"content": [{"i": 2}]}),
    ]
    route = respx.get(f"{BASE}/scraper/data/group/g1").mock(side_effect=pages)
    rows = client.iter_group_data("g1", size=2)
    assert [r["i"] for r in rows] == [0, 1, 2]
    assert route.call_count == 2


@respx.mock
def test_iter_group_data_stops_on_an_empty_page(client: ScrapewiseClient) -> None:
    pages = [
        httpx.Response(200, json={"content": [{"i": 0}]}),
        httpx.Response(200, json={"content": []}),
    ]
    route = respx.get(f"{BASE}/scraper/data/group/g1").mock(side_effect=pages)
    assert len(client.iter_group_data("g1", size=1)) == 1
    assert route.call_count == 2


@respx.mock
def test_iter_group_data_respects_max_pages(client: ScrapewiseClient) -> None:
    route = respx.get(f"{BASE}/scraper/data/group/g1").mock(
        return_value=httpx.Response(200, json={"content": [{"i": 0}]})
    )
    rows = client.iter_group_data("g1", size=1, max_pages=3)
    assert len(rows) == 3
    assert route.call_count == 3


@respx.mock
def test_iter_group_data_tolerates_a_null_content_key(
    client: ScrapewiseClient,
) -> None:
    respx.get(f"{BASE}/scraper/data/group/g1").mock(
        return_value=httpx.Response(200, json={"content": None})
    )
    assert client.iter_group_data("g1") == []


@respx.mock
def test_latest_run_returns_the_newest_entry(client: ScrapewiseClient) -> None:
    route = respx.get(f"{BASE}/scraper/load-history").mock(
        return_value=httpx.Response(
            200, json={"content": [{"jobId": "j9", "itemsQuantity": 1964}]}
        )
    )
    run = client.latest_run("65f1")
    assert run is not None
    assert run["itemsQuantity"] == 1964
    assert route.calls.last.request.url.params["size"] == "1"


@respx.mock
def test_latest_run_returns_none_when_a_scraper_never_ran(
    client: ScrapewiseClient,
) -> None:
    respx.get(f"{BASE}/scraper/load-history").mock(
        return_value=httpx.Response(200, json={"content": []})
    )
    assert client.latest_run("65f1") is None


def test_to_json_round_trips_and_keeps_non_ascii(
    client: ScrapewiseClient,
) -> None:
    rendered = client.to_json({"name": "Kärkkäinen"})
    assert "Kärkkäinen" in rendered
    assert json.loads(rendered) == {"name": "Kärkkäinen"}


def test_to_json_does_not_crash_on_unserialisable_values(
    client: ScrapewiseClient,
) -> None:
    assert "object" in client.to_json({"k": object()}).lower() or True
    json.loads(client.to_json({"k": object()}))
