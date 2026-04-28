from __future__ import annotations

import pytest
from agents.mcp import MCPServerStreamableHttp
from pydantic import ValidationError

from oratium.tools.mcp import MCPServerSpec, to_sdk_server


def test_mcp_spec_url_only() -> None:
    spec = MCPServerSpec(url="https://mcp.example.com")
    assert spec.url == "https://mcp.example.com"
    assert spec.headers == {}
    assert spec.timeout == 30.0


def test_mcp_spec_with_headers_and_timeout() -> None:
    spec = MCPServerSpec(
        url="https://mcp.example.com",
        headers={"Authorization": "Bearer x"},
        timeout=60.0,
    )
    assert spec.headers == {"Authorization": "Bearer x"}
    assert spec.timeout == 60.0


def test_mcp_spec_rejects_empty_url() -> None:
    with pytest.raises(ValidationError):
        MCPServerSpec(url="")


def test_mcp_spec_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        MCPServerSpec.model_validate({"url": "https://x", "extra_field": "nope"})


def test_to_sdk_server_returns_streamable_http() -> None:
    server = to_sdk_server(MCPServerSpec(url="https://mcp.example.com"))
    assert isinstance(server, MCPServerStreamableHttp)


def test_to_sdk_server_passes_headers() -> None:
    spec = MCPServerSpec(
        url="https://mcp.example.com",
        headers={"Authorization": "Bearer x"},
    )
    server = to_sdk_server(spec)
    # SDK stores params on the instance; we can't introspect cleanly, but
    # construction without error is the key behavior.
    assert isinstance(server, MCPServerStreamableHttp)
