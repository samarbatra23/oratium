from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oratium.agent import Agent
from oratium.app import OratiumApp
from oratium.storage.yaml_store import YAMLTenantStore

TWO_TENANT_YAML = """\
tenants:
  - id: support
    twilio_number: "+15555550100"
    agent:
      name: Support
      instructions: Help politely.
      voice: alloy
  - id: sales
    twilio_number: "+15555550200"
    agent:
      name: Sales
      instructions: Be enthusiastic.
      voice: verse
"""


@pytest.fixture
def store(tmp_path: Path) -> YAMLTenantStore:
    p = tmp_path / "tenants.yaml"
    p.write_text(TWO_TENANT_YAML)
    return YAMLTenantStore(p)


# --- constructor validation ---


def test_requires_exactly_one_of_agent_or_tenants(
    monkeypatch: pytest.MonkeyPatch, store: YAMLTenantStore
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with pytest.raises(ValueError, match="exactly one"):
        OratiumApp()  # neither
    with pytest.raises(ValueError, match="exactly one"):
        OratiumApp(agent=Agent(name="x"), tenants=store)  # both


def test_constructs_in_multi_tenant_mode(
    monkeypatch: pytest.MonkeyPatch, store: YAMLTenantStore
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(tenants=store)
    assert app.fastapi is not None


# --- multi-tenant webhook routing ---


def test_routes_known_number_to_correct_tenant(
    monkeypatch: pytest.MonkeyPatch, store: YAMLTenantStore
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(tenants=store)
    client = TestClient(app.fastapi)

    response = client.post(
        "/incoming-call",
        headers={"Host": "example.com"},
        data={"To": "+15555550100", "From": "+12025551234"},
    )
    assert response.status_code == 200
    assert "<Connect>" in response.text
    assert "wss://example.com/media-stream/support" in response.text


def test_routes_second_number_to_second_tenant(
    monkeypatch: pytest.MonkeyPatch, store: YAMLTenantStore
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(tenants=store)
    client = TestClient(app.fastapi)

    response = client.post(
        "/incoming-call",
        headers={"Host": "example.com"},
        data={"To": "+15555550200"},
    )
    assert "wss://example.com/media-stream/sales" in response.text


def test_unknown_number_returns_no_tenant_twiml(
    monkeypatch: pytest.MonkeyPatch, store: YAMLTenantStore
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(tenants=store)
    client = TestClient(app.fastapi)

    response = client.post(
        "/incoming-call",
        headers={"Host": "example.com"},
        data={"To": "+19999999999"},
    )
    assert response.status_code == 200
    assert "not currently configured" in response.text
    assert "<Hangup" in response.text


def test_missing_to_param_returns_no_tenant_twiml(
    monkeypatch: pytest.MonkeyPatch, store: YAMLTenantStore
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(tenants=store)
    client = TestClient(app.fastapi)

    response = client.post("/incoming-call", headers={"Host": "example.com"}, data={})
    assert "not currently configured" in response.text


def test_get_with_to_query_param_works(
    monkeypatch: pytest.MonkeyPatch, store: YAMLTenantStore
) -> None:
    """Some Twilio configurations use GET with query params."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(tenants=store)
    client = TestClient(app.fastapi)

    response = client.get(
        "/incoming-call?To=%2B15555550100",
        headers={"Host": "example.com"},
    )
    assert "wss://example.com/media-stream/support" in response.text


# --- single-tenant mode unchanged ---


def test_single_tenant_mode_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 1 backward compat: agent= still produces a working app."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(agent=Agent(name="hi"))
    client = TestClient(app.fastapi)

    response = client.post("/incoming-call", headers={"Host": "example.com"})
    assert response.status_code == 200
    # Single-tenant URL has no tenant suffix at all.
    assert 'url="wss://example.com/media-stream"' in response.text
