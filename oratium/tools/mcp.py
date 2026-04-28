"""MCP server configuration — passthrough to the SDK's HTTP MCP transport."""

from __future__ import annotations

from typing import Any, cast

from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from pydantic import BaseModel, ConfigDict, Field


class MCPServerSpec(BaseModel):
    """Configuration for an HTTP-based MCP server.

    Plain string entries in ``UnifiedTools.mcp_servers`` are auto-promoted
    to ``MCPServerSpec(url=that_string)``; richer entries can carry
    headers and a custom timeout.
    """

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: float = 30.0


def to_sdk_server(spec: MCPServerSpec) -> MCPServerStreamableHttp:
    """Build an SDK :class:`MCPServerStreamableHttp` from a spec."""
    params: dict[str, Any] = {"url": spec.url}
    if spec.headers:
        params["headers"] = spec.headers
    if spec.timeout != 30.0:
        params["timeout"] = spec.timeout
    return MCPServerStreamableHttp(params=cast(MCPServerStreamableHttpParams, params))
