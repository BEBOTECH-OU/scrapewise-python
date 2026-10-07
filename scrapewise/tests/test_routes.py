"""One test per wrapped route: asserts method, path, params and body.

The point of these is not that httpx works -- it is that the URL this client
builds is the documented one, because a wrong path on this API returns 404 or
500 rather than anything self-describing.
"""

from __future__ import annotations

import json

import httpx
import respx

from scrapewise import DEFAULT_BASE_URL, LOAD_SITE_TIMEOUT, ScrapewiseClient

BASE = DEFAULT_BASE_URL


def _body(route) -> dict:
    return json.loads(route.calls.last.request.content.decode())


# ----------------------------------------------------------------------
# scrapers
# ----------------------------------------------------------------------


@respx.mock
def test_list_scrapers_hits_scraper_list(client: ScrapewiseClient) -> None:
    respx.get(f"{BASE}/scraper/list").mock(
        return_value=httpx.Response(200, json=[{"id": "a"}, {"id": "b"}])
    )
    assert [s["id"] for s in client.list_scrapers()] == ["a", "b"]


@respx.mock
def test_list_scrapers_unwraps_a_paginated_envelope(
    client: ScrapewiseClient,
) -> None:
    respx.get(f"{BASE}/scraper/list").mock(
        return_value=httpx.Response(200, json={"content": [{"id": "a"}]})
    )
    assert client.list_scrapers() == [{"id": "a"}]


@respx.mock
def test_get_scraper_hits_scraper_by_id(client: ScrapewiseClient) -> None:
    respx.get(f"{BASE}/scraper/65f1").mock(
        return_value=httpx.Response(200, json={"id": "65f1", "schemaId": "s1"})
    )
    assert client.get_scraper("65f1")["schemaId"] == "s1"


@respx.mock
def test_upsert_scraper_puts_the_dto_verbatim(client: ScrapewiseClient) -> None:
    route = respx.put(f"{BASE}/scraper").mock(
        return_value=httpx.Response(200, json={"id": "new"})
    )
    client.upsert_scraper({"name": "shop", "config": {"itemsConfig": []}})
    assert _body(route) == {"name": "shop", "config": {"itemsConfig": []}}


@respx.mock
def test_run_scraper_hits_the_run_route(client: ScrapewiseClient) -> None:
    route = respx.get(f"{BASE}/scraper/65f1/run").mock(
        return_value=httpx.Response(200, json={"state": "PENDING"})
    )
    client.run_scraper("65f1")
    assert route.called


@respx.mock
def test_get_sample_data_passes_prefer_persisted(client: ScrapewiseClient) -> None:
    route = respx.get(f"{BASE}/scraper/65f1/get-sample-data").mock(
        return_value=httpx.Response(200, json=[{"title": "x"}])
    )
    client.get_sample_data("65f1", prefer_persisted=True)
    assert route.calls.last.request.url.params["preferPersisted"] == "true"


@respx.mock
def test_attach_schema_patches_with_a_schema_id_body(
    client: ScrapewiseClient,
) -> None:
    route = respx.patch(f"{BASE}/scraper/65f1/schema").mock(
        return_value=httpx.Response(200, json={"id": "65f1", "schemaId": "v50"})
    )
    client.attach_schema("65f1", "v50")
    assert _body(route) == {"schemaId": "v50"}


# ----------------------------------------------------------------------
# sites and links
# ----------------------------------------------------------------------


@respx.mock
def test_get_scraper_site_hits_the_scraper_scoped_site_route(
    client: ScrapewiseClient,
) -> None:
    respx.get(f"{BASE}/scraper/65f1/site").mock(
        return_value=httpx.Response(200, json={"id": "site1", "linkCount": 12})
    )
    assert client.get_scraper_site("65f1")["id"] == "site1"


@respx.mock
def test_list_site_links_uses_the_site_id_and_paging_params(
    client: ScrapewiseClient,
) -> None:
    route = respx.get(f"{BASE}/scraper/site/site1/links").mock(
        return_value=httpx.Response(200, json={"content": [{"url": "u"}]})
    )
    client.list_site_links("site1", page=2, size=200)
    params = route.calls.last.request.url.params
    assert params["page"] == "2"
    assert params["size"] == "200"
    assert params["sortField"]
    assert params["sortDirection"]


@respx.mock
def test_replace_site_links_reuses_an_existing_site_id(
    client: ScrapewiseClient,
) -> None:
    route = respx.put(f"{BASE}/scraper/site").mock(
        return_value=httpx.Response(200, json={"id": "site1"})
    )
    client.replace_site_links(
        "65f1", [{"title": "ean", "url": "https://shop.test/p/1"}], site_id="site1"
    )
    assert _body(route) == {
        "scraperId": "65f1",
        "links": [{"title": "ean", "url": "https://shop.test/p/1"}],
        "id": "site1",
    }


@respx.mock
def test_replace_site_links_omits_id_when_none_given(
    client: ScrapewiseClient,
) -> None:
    route = respx.put(f"{BASE}/scraper/site").mock(
        return_value=httpx.Response(200, json={"id": "fresh"})
    )
    client.replace_site_links("65f1", [])
    assert "id" not in _body(route)


@respx.mock
def test_load_site_returns_text_and_defaults_to_a_longer_timeout(
    client: ScrapewiseClient,
) -> None:
    route = respx.get(f"{BASE}/scraper/load-site").mock(
        return_value=httpx.Response(200, text="<html>hi</html>")
    )
    assert client.load_site("https://shop.test/p/1") == "<html>hi</html>"
    request = route.calls.last.request
    assert request.url.params["url"] == "https://shop.test/p/1"
    assert request.extensions["timeout"]["read"] == LOAD_SITE_TIMEOUT


# ----------------------------------------------------------------------
# groups
# ----------------------------------------------------------------------


@respx.mock
def test_list_groups_hits_group_list(client: ScrapewiseClient) -> None:
    respx.get(f"{BASE}/scraper/group/list").mock(
        return_value=httpx.Response(200, json=[{"id": "g1"}])
    )
    assert client.list_groups() == [{"id": "g1"}]


@respx.mock
def test_upsert_group_puts_the_dto(client: ScrapewiseClient) -> None:
    route = respx.put(f"{BASE}/scraper/group").mock(
        return_value=httpx.Response(200, json={"id": "g1"})
    )
    client.upsert_group({"name": "DE prices"})
    assert _body(route) == {"name": "DE prices"}


@respx.mock
def test_set_group_currency_sends_the_idempotency_key_when_given(
    client: ScrapewiseClient,
) -> None:
    route = respx.put(f"{BASE}/scraper/group/g1/currency").mock(
        return_value=httpx.Response(200, json={})
    )
    client.set_group_currency("g1", "EUR", idempotency_key="abc-123")
    request = route.calls.last.request
    assert request.headers["idempotency-key"] == "abc-123"
    assert json.loads(request.content.decode()) == {"currency": "EUR"}


@respx.mock
def test_set_group_currency_omits_the_header_when_not_given(
    client: ScrapewiseClient,
) -> None:
    route = respx.put(f"{BASE}/scraper/group/g1/currency").mock(
        return_value=httpx.Response(200, json={})
    )
    client.set_group_currency("g1", "EUR")
    assert "idempotency-key" not in route.calls.last.request.headers


@respx.mock
def test_get_group_data_hits_the_data_group_route(
    client: ScrapewiseClient,
) -> None:
    route = respx.get(f"{BASE}/scraper/data/group/g1").mock(
        return_value=httpx.Response(200, json={"content": [{"title": "x"}]})
    )
    page = client.get_group_data("g1", page=1, size=50)
    assert page["content"] == [{"title": "x"}]
    params = route.calls.last.request.url.params
    assert params["page"] == "1"
    assert params["size"] == "50"


@respx.mock
def test_get_group_post_process_rules_returns_the_version(
    client: ScrapewiseClient,
) -> None:
    respx.get(f"{BASE}/scraper/group/g1/post-process-rules").mock(
        return_value=httpx.Response(
            200, json={"groupId": "g1", "rules": [], "scraperValues": {}, "version": 7}
        )
    )
    assert client.get_group_post_process_rules("g1")["version"] == 7


@respx.mock
def test_update_group_rules_renames_version_to_expected_version(
    client: ScrapewiseClient,
) -> None:
    route = respx.put(f"{BASE}/scraper/group/g1/post-process-rules").mock(
        return_value=httpx.Response(200, json={"version": 8})
    )
    client.update_group_post_process_rules(
        "g1",
        rules=[{"kind": "NUMBER_EXTRACT"}],
        scraper_values={"65f1": {}},
        expected_version=7,
    )
    body = _body(route)
    assert body["expectedVersion"] == 7
    assert "version" not in body
    assert body["rules"] == [{"kind": "NUMBER_EXTRACT"}]
    assert body["scraperValues"] == {"65f1": {}}


# ----------------------------------------------------------------------
# runs and diagnostics
# ----------------------------------------------------------------------


@respx.mock
def test_get_load_history_passes_the_scraper_id_as_a_query_param(
    client: ScrapewiseClient,
) -> None:
    route = respx.get(f"{BASE}/scraper/load-history").mock(
        return_value=httpx.Response(200, json={"content": []})
    )
    client.get_load_history("65f1")
    assert route.calls.last.request.url.params["scraperId"] == "65f1"


@respx.mock
def test_get_job_errors_hits_the_group_and_job_scoped_route(
    client: ScrapewiseClient,
) -> None:
    route = respx.get(
        f"{BASE}/scraper/load-history/group/g1/job/j1/errors"
    ).mock(return_value=httpx.Response(200, json={"content": []}))
    client.get_job_errors("g1", "j1")
    assert route.called


@respx.mock
def test_preview_rule_posts_rule_and_sample_value(
    client: ScrapewiseClient,
) -> None:
    route = respx.post(f"{BASE}/scraper/preview-rule").mock(
        return_value=httpx.Response(200, json={"output": "12.90"})
    )
    client.preview_rule({"kind": "NUMBER_EXTRACT"}, "12,90 EUR")
    assert _body(route) == {
        "rule": {"kind": "NUMBER_EXTRACT"},
        "sampleValue": "12,90 EUR",
    }


# ----------------------------------------------------------------------
# schemas and desktops
# ----------------------------------------------------------------------


@respx.mock
def test_list_customer_schemas_hits_schema_customer(
    client: ScrapewiseClient,
) -> None:
    respx.get(f"{BASE}/schema/customer").mock(
        return_value=httpx.Response(200, json=[{"id": "s1"}])
    )
    assert client.list_customer_schemas() == [{"id": "s1"}]


@respx.mock
def test_get_schema_hits_schema_get_by_id(client: ScrapewiseClient) -> None:
    respx.get(f"{BASE}/schema/get/s1").mock(
        return_value=httpx.Response(200, json={"id": "s1", "content": {}})
    )
    assert "content" in client.get_schema("s1")


@respx.mock
def test_publish_customer_schema_puts_the_document(
    client: ScrapewiseClient,
) -> None:
    route = respx.put(f"{BASE}/schema/customer").mock(
        return_value=httpx.Response(200, json={"id": "s2"})
    )
    client.publish_customer_schema({"content": {"required": ["price"]}})
    assert _body(route) == {"content": {"required": ["price"]}}


@respx.mock
def test_list_desktops_hits_scraper_desktop(client: ScrapewiseClient) -> None:
    respx.get(f"{BASE}/scraper/desktop").mock(
        return_value=httpx.Response(200, json=[{"id": "d1", "order": 0}])
    )
    assert client.list_desktops()[0]["id"] == "d1"
