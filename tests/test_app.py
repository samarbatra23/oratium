from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from oratium.agent import Agent
from oratium.app import OratiumApp


def test_constructs_with_env_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(agent=Agent(name="hi"))
    assert app.fastapi is not None


def test_constructs_with_explicit_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = OratiumApp(agent=Agent(name="hi"), api_key="sk-explicit")
    assert app.fastapi is not None


def test_raises_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OratiumApp(agent=Agent(name="hi"))


def test_root_endpoint_returns_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(agent=Agent(name="hi"))
    client = TestClient(app.fastapi)

    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "oratium"


def test_incoming_call_returns_twiml_with_stream_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(agent=Agent(name="hi"))
    client = TestClient(app.fastapi)

    response = client.post("/incoming-call", headers={"Host": "example.com"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/xml")
    assert "<Connect>" in response.text
    assert "wss://example.com/media-stream" in response.text


def test_incoming_call_works_with_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(agent=Agent(name="hi"))
    client = TestClient(app.fastapi)

    response = client.get("/incoming-call", headers={"Host": "example.com"})
    assert response.status_code == 200
    assert "wss://example.com/media-stream" in response.text


def test_custom_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(
        agent=Agent(name="hi"),
        incoming_call_path="/voice",
        media_stream_path="/stream",
    )
    client = TestClient(app.fastapi)

    assert client.get("/incoming-call").status_code == 404
    response = client.post("/voice", headers={"Host": "example.com"})
    assert response.status_code == 200
    assert "wss://example.com/stream" in response.text


def test_app_is_asgi_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    """OratiumApp must be ASGI-callable so ``uvicorn module:app`` works directly."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = OratiumApp(agent=Agent(name="hi"))

    client = TestClient(app)  # passing the OratiumApp instance, not .fastapi
    response = client.get("/")
    assert response.status_code == 200
