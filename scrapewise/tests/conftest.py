"""Shared fixtures. No test in this suite touches the network."""

from __future__ import annotations

import pytest

from scrapewise import DEFAULT_BASE_URL, ScrapewiseClient

API_KEY = "YOUR_SCRAPEWISE_API_KEY"
BASE = DEFAULT_BASE_URL


@pytest.fixture(autouse=True)
def _no_ambient_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's real shell env out of the suite."""
    monkeypatch.delenv("SCRAPEWISE_API_KEY", raising=False)
    monkeypatch.delenv("SCRAPEWISE_BASE_URL", raising=False)


@pytest.fixture()
def client() -> ScrapewiseClient:
    with ScrapewiseClient(api_key=API_KEY) as sw:
        yield sw
