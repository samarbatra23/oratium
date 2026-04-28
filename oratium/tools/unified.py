"""``UnifiedTools`` — heterogeneous capability collector for an agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from oratium.tools.data_tables import DataTable, make_query_function
from oratium.tools.knowledge import (
    EmbedFn,
    KnowledgeIndex,
    make_openai_embedder,
    make_search_function,
)
from oratium.tools.mcp import MCPServerSpec, to_sdk_server


@dataclass(slots=True)
class UnifiedTools:
    """Collect functions, knowledge sources, data tables, and MCP servers.

    All four categories desugar into the SDK's ``tools`` and ``mcp_servers``
    parameters via :meth:`to_realtime_tools` and :meth:`to_mcp_servers`.

    Attributes:
        functions: ``@function_tool``-decorated callables (or anything the
            SDK accepts as a tool). Passed through unchanged.
        knowledge: PDF paths or web URLs. Each is ingested lazily on
            first search and exposed as a single ``search_knowledge``
            function tool.
        data_tables: In-memory row sets. Each becomes a synthesized
            ``query_<name>`` function tool.
        mcp_servers: MCP server URLs (or :class:`MCPServerSpec` instances
            for headers / timeouts). Forwarded to the SDK's
            ``mcp_servers=`` parameter as
            :class:`MCPServerStreamableHttp` instances.
    """

    functions: list[Callable[..., Any]] = field(default_factory=list)
    knowledge: list[str] = field(default_factory=list)
    data_tables: list[DataTable] = field(default_factory=list)
    mcp_servers: list[str | MCPServerSpec] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validate_unique_tool_names()

    def _validate_unique_tool_names(self) -> None:
        names: list[str] = []
        for func in self.functions:
            name = getattr(func, "name", None) or getattr(func, "__name__", None) or str(func)
            names.append(str(name))
        if self.knowledge:
            names.append("search_knowledge")
        for table in self.data_tables:
            names.append(f"query_{table.name}")
        seen: set[str] = set()
        for n in names:
            if n in seen:
                raise ValueError(
                    f"Duplicate tool name {n!r} in UnifiedTools — function names, "
                    "search_knowledge (when knowledge sources are configured), and "
                    "query_<table_name> must all be distinct."
                )
            seen.add(n)

    def to_realtime_tools(
        self,
        *,
        api_key: str | None = None,
        embedder: EmbedFn | None = None,
    ) -> list[Any]:
        """Resolve functions, knowledge, and data tables to SDK tool list.

        ``api_key`` is required only if knowledge sources are configured
        and no explicit ``embedder`` is provided. Tests inject a fake
        ``embedder`` to avoid OpenAI calls.
        """
        tools: list[Any] = list(self.functions)

        if self.knowledge:
            embed_fn = embedder
            if embed_fn is None:
                if not api_key:
                    raise ValueError(
                        "knowledge sources require api_key= or an explicit "
                        "embedder= to build the OpenAI embedder."
                    )
                embed_fn = make_openai_embedder(api_key)
            index = KnowledgeIndex(sources=self.knowledge, embed=embed_fn)
            tools.append(make_search_function(index))

        for table in self.data_tables:
            tools.append(make_query_function(table))

        return tools

    def to_mcp_servers(self) -> list[Any]:
        """Resolve MCP server specs to SDK :class:`MCPServerStreamableHttp` list."""
        servers: list[Any] = []
        for entry in self.mcp_servers:
            spec = entry if isinstance(entry, MCPServerSpec) else MCPServerSpec(url=entry)
            servers.append(to_sdk_server(spec))
        return servers
