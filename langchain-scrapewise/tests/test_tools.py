"""Schema and dispatch tests for the ScrapeWise LangChain tools.

The client is replaced by a recorder, so nothing here touches the network and
no API key is needed.
"""

from __future__ import annotations

import json
from typing import Any, List, Tuple

import pytest
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from langchain_scrapewise import (
    SCRAPEWISE_TOOL_CLASSES,
    ScrapewiseBaseTool,
    ScrapewiseGetScraperSiteTool,
    ScrapewiseGetScraperTool,
    ScrapewiseGroupDataTool,
    ScrapewiseGroupRulesTool,
    ScrapewiseListGroupsTool,
    ScrapewiseListSchemasTool,
    ScrapewiseListScrapersTool,
    ScrapewisePreviewRuleTool,
    ScrapewiseRunHistoryTool,
    ScrapewiseRunScraperTool,
    ScrapewiseSampleDataTool,
    ScrapewiseSiteLinksTool,
    ScrapewiseToolkit,
    __version__,
)
from langchain_scrapewise.base import MAX_CHARS


class FakeClient:
    """Records every call and returns an echo of it."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, tuple, dict]] = []
        self.returns: Any = None

    def __getattr__(self, name: str) -> Any:
        def _recorder(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args, kwargs))
            if self.returns is not None:
                return self.returns
            return {"method": name, "args": list(args), "kwargs": kwargs}

        return _recorder


@pytest.fixture()
def fake() -> FakeClient:
    return FakeClient()


def _tool(cls: Any, fake: FakeClient) -> ScrapewiseBaseTool:
    return cls(client=fake)


# ----------------------------------------------------------------------
# package surface
# ----------------------------------------------------------------------


def test_version_is_exported() -> None:
    assert __version__ == "0.1.0"


def test_tool_class_tuple_has_no_duplicates() -> None:
    assert len(set(SCRAPEWISE_TOOL_CLASSES)) == len(SCRAPEWISE_TOOL_CLASSES)


# ----------------------------------------------------------------------
# every tool, structurally
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls", SCRAPEWISE_TOOL_CLASSES, ids=lambda c: c.__name__
)
def test_every_tool_instantiates_without_credentials(
    cls: Any, fake: FakeClient
) -> None:
    tool = _tool(cls, fake)
    assert isinstance(tool, BaseTool)
    assert isinstance(tool, ScrapewiseBaseTool)


@pytest.mark.parametrize(
    "cls", SCRAPEWISE_TOOL_CLASSES, ids=lambda c: c.__name__
)
def test_every_tool_has_a_namespaced_name(cls: Any, fake: FakeClient) -> None:
    name = _tool(cls, fake).name
    assert name.startswith("scrapewise_")
    assert name == name.lower()
    assert " " not in name


def test_tool_names_are_unique(fake: FakeClient) -> None:
    names = [_tool(cls, fake).name for cls in SCRAPEWISE_TOOL_CLASSES]
    assert len(set(names)) == len(names)


@pytest.mark.parametrize(
    "cls", SCRAPEWISE_TOOL_CLASSES, ids=lambda c: c.__name__
)
def test_every_description_is_model_facing(cls: Any, fake: FakeClient) -> None:
    description = _tool(cls, fake).description
    assert 60 < len(description) < 600, len(description)
    assert "ScrapeWise" in description


@pytest.mark.parametrize(
    "cls", SCRAPEWISE_TOOL_CLASSES, ids=lambda c: c.__name__
)
def test_every_tool_declares_a_pydantic_args_schema(
    cls: Any, fake: FakeClient
) -> None:
    schema = _tool(cls, fake).args_schema
    assert isinstance(schema, type) and issubclass(schema, BaseModel)
    assert "properties" in schema.model_json_schema() or not schema.model_fields


@pytest.mark.parametrize(
    "cls", SCRAPEWISE_TOOL_CLASSES, ids=lambda c: c.__name__
)
def test_every_declared_argument_is_described(
    cls: Any, fake: FakeClient
) -> None:
    """A field with no description reaches the model as a bare name."""
    for name, field in _tool(cls, fake).args_schema.model_fields.items():
        assert field.description, f"{cls.__name__}.{name} has no description"


@pytest.mark.parametrize(
    "cls", SCRAPEWISE_TOOL_CLASSES, ids=lambda c: c.__name__
)
def test_every_tool_is_bindable_as_an_openai_function(
    cls: Any, fake: FakeClient
) -> None:
    """What ``llm.bind_tools([...])`` does under the hood."""
    from langchain_core.utils.function_calling import convert_to_openai_tool

    spec = convert_to_openai_tool(_tool(cls, fake))
    assert spec["type"] == "function"
    assert spec["function"]["name"].startswith("scrapewise_")
    assert spec["function"]["description"]
    assert spec["function"]["parameters"]["type"] == "object"


# ----------------------------------------------------------------------
# per-tool argument schemas
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (ScrapewiseListScrapersTool, set()),
        (ScrapewiseListGroupsTool, set()),
        (ScrapewiseListSchemasTool, set()),
        (ScrapewiseGetScraperTool, {"scraper_id"}),
        (ScrapewiseRunScraperTool, {"scraper_id"}),
        (ScrapewiseGetScraperSiteTool, {"scraper_id"}),
        (ScrapewiseSampleDataTool, {"scraper_id", "prefer_persisted"}),
        (ScrapewiseRunHistoryTool, {"scraper_id", "size"}),
        (ScrapewiseGroupDataTool, {"group_id", "page", "size"}),
        (ScrapewiseGroupRulesTool, {"group_id"}),
        (ScrapewiseSiteLinksTool, {"site_id", "page", "size"}),
        (ScrapewisePreviewRuleTool, {"rule", "sample_value"}),
    ],
    ids=lambda v: v.__name__ if isinstance(v, type) else str(sorted(v)),
)
def test_argument_names_are_exactly_as_expected(
    cls: Any, expected: set, fake: FakeClient
) -> None:
    assert set(_tool(cls, fake).args_schema.model_fields) == expected


def test_required_arguments_are_required(fake: FakeClient) -> None:
    schema = _tool(ScrapewiseGroupDataTool, fake).args_schema.model_json_schema()
    assert schema["required"] == ["group_id"]


def test_page_size_is_bounded(fake: FakeClient) -> None:
    properties = _tool(
        ScrapewiseGroupDataTool, fake
    ).args_schema.model_json_schema()["properties"]
    assert properties["size"]["minimum"] == 1
    assert properties["size"]["maximum"] == 200


# ----------------------------------------------------------------------
# dispatch
# ----------------------------------------------------------------------


def test_list_scrapers_calls_the_client(fake: FakeClient) -> None:
    out = _tool(ScrapewiseListScrapersTool, fake).invoke({})
    assert fake.calls == [("list_scrapers", (), {})]
    assert json.loads(out)["method"] == "list_scrapers"


def test_get_scraper_forwards_the_id(fake: FakeClient) -> None:
    _tool(ScrapewiseGetScraperTool, fake).invoke({"scraper_id": "65f1"})
    assert fake.calls == [("get_scraper", ("65f1",), {})]


def test_run_scraper_forwards_the_id(fake: FakeClient) -> None:
    _tool(ScrapewiseRunScraperTool, fake).invoke({"scraper_id": "65f1"})
    assert fake.calls == [("run_scraper", ("65f1",), {})]


def test_sample_data_sends_none_rather_than_false(fake: FakeClient) -> None:
    """``preferPersisted=false`` and an absent param are not the same request."""
    _tool(ScrapewiseSampleDataTool, fake).invoke({"scraper_id": "65f1"})
    assert fake.calls[0][2] == {"prefer_persisted": None}


def test_sample_data_passes_prefer_persisted_through(fake: FakeClient) -> None:
    _tool(ScrapewiseSampleDataTool, fake).invoke(
        {"scraper_id": "65f1", "prefer_persisted": True}
    )
    assert fake.calls[0][2] == {"prefer_persisted": True}


def test_run_history_defaults_to_five_recent_runs(fake: FakeClient) -> None:
    _tool(ScrapewiseRunHistoryTool, fake).invoke({"scraper_id": "65f1"})
    assert fake.calls[0] == ("get_load_history", ("65f1",), {"page": 0, "size": 5})


def test_group_data_forwards_paging(fake: FakeClient) -> None:
    _tool(ScrapewiseGroupDataTool, fake).invoke(
        {"group_id": "g1", "page": 2, "size": 10}
    )
    assert fake.calls[0] == ("get_group_data", ("g1",), {"page": 2, "size": 10})


def test_site_links_forwards_paging(fake: FakeClient) -> None:
    _tool(ScrapewiseSiteLinksTool, fake).invoke({"site_id": "site1"})
    assert fake.calls[0] == (
        "list_site_links",
        ("site1",),
        {"page": 0, "size": 50},
    )


def test_group_rules_calls_the_read_route(fake: FakeClient) -> None:
    _tool(ScrapewiseGroupRulesTool, fake).invoke({"group_id": "g1"})
    assert fake.calls[0][0] == "get_group_post_process_rules"


def test_preview_rule_forwards_rule_and_value(fake: FakeClient) -> None:
    _tool(ScrapewisePreviewRuleTool, fake).invoke(
        {"rule": {"postProcessKind": "NUMBER_EXTRACT"}, "sample_value": "12,90 EUR"}
    )
    assert fake.calls[0] == (
        "preview_rule",
        ({"postProcessKind": "NUMBER_EXTRACT"}, "12,90 EUR"),
        {},
    )


def test_an_invalid_argument_is_rejected_before_any_client_call(
    fake: FakeClient,
) -> None:
    from pydantic import ValidationError

    with pytest.raises((ValidationError, ValueError)):
        _tool(ScrapewiseGroupDataTool, fake).invoke(
            {"group_id": "g1", "size": 9999}
        )
    assert fake.calls == []


# ----------------------------------------------------------------------
# response shaping
# ----------------------------------------------------------------------


def test_output_is_json_text(fake: FakeClient) -> None:
    fake.returns = [{"id": "a"}]
    out = _tool(ScrapewiseListScrapersTool, fake).invoke({})
    assert isinstance(out, str)
    assert json.loads(out) == [{"id": "a"}]


def test_a_huge_payload_is_truncated_with_a_visible_marker(
    fake: FakeClient,
) -> None:
    fake.returns = [{"blob": "x" * 200} for _ in range(500)]
    out = _tool(ScrapewiseGroupDataTool, fake).invoke({"group_id": "g1"})
    assert "truncated" in out
    assert len(out) < MAX_CHARS + 200


def test_an_api_error_is_returned_as_text_not_raised() -> None:
    from scrapewise import ScrapewiseNotFoundError

    class Failing:
        def get_scraper(self, *_: Any, **__: Any) -> Any:
            raise ScrapewiseNotFoundError(
                "no such scraper", status_code=404, body='{"message":"not found"}'
            )

    out = _tool(ScrapewiseGetScraperTool, Failing()).invoke(
        {"scraper_id": "nope"}
    )
    payload = json.loads(out)
    assert payload["error"] == "ScrapewiseNotFoundError"
    assert payload["status"] == 404


def test_non_ascii_survives_the_dump(fake: FakeClient) -> None:
    fake.returns = {"name": "Kärkkäinen"}
    out = _tool(ScrapewiseGetScraperTool, fake).invoke({"scraper_id": "x"})
    assert "Kärkkäinen" in out


# ----------------------------------------------------------------------
# toolkit
# ----------------------------------------------------------------------


def test_toolkit_returns_every_tool(fake: FakeClient) -> None:
    tools = ScrapewiseToolkit(client=fake).get_tools()
    assert len(tools) == len(SCRAPEWISE_TOOL_CLASSES)
    assert {type(t) for t in tools} == set(SCRAPEWISE_TOOL_CLASSES)


def test_toolkit_shares_one_client_across_tools(fake: FakeClient) -> None:
    tools = ScrapewiseToolkit(client=fake).get_tools()
    assert {id(t.client) for t in tools} == {id(fake)}


def test_toolkit_tools_are_all_bindable(fake: FakeClient) -> None:
    from langchain_core.utils.function_calling import convert_to_openai_tool

    specs = [convert_to_openai_tool(t) for t in ScrapewiseToolkit(client=fake).get_tools()]
    assert len({s["function"]["name"] for s in specs}) == len(specs)


# ----------------------------------------------------------------------
# credentials
# ----------------------------------------------------------------------


def test_a_tool_without_a_key_fails_only_when_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Declaring a tool must not require credentials to be present."""
    from scrapewise import ScrapewiseConfigurationError

    monkeypatch.delenv("SCRAPEWISE_API_KEY", raising=False)
    tool = ScrapewiseListScrapersTool()
    with pytest.raises(ScrapewiseConfigurationError):
        _ = tool.client


def test_api_key_is_passed_to_the_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SCRAPEWISE_API_KEY", raising=False)
    tool = ScrapewiseListScrapersTool(api_key="YOUR_SCRAPEWISE_API_KEY")
    assert tool.client._headers()["Authorization"].endswith(
        "YOUR_SCRAPEWISE_API_KEY"
    )


def test_base_url_override_reaches_the_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SCRAPEWISE_BASE_URL", raising=False)
    tool = ScrapewiseListScrapersTool(
        api_key="k", base_url="https://staging.test/api"
    )
    assert tool.client.base_url == "https://staging.test/api"


def test_the_api_key_is_excluded_from_serialisation() -> None:
    tool = ScrapewiseListScrapersTool(api_key="super-secret")
    assert "super-secret" not in json.dumps(tool.model_dump(), default=str)
