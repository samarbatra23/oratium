from __future__ import annotations

import pytest
from agents import function_tool
from agents.mcp import MCPServerStreamableHttp

from oratium.tools.data_tables import DataTable
from oratium.tools.mcp import MCPServerSpec
from oratium.tools.unified import UnifiedTools


@function_tool
def _example_func(x: int) -> int:
    """Example function tool used in tests."""
    return x * 2


@function_tool
def _another_func(y: str) -> str:
    """Another example."""
    return y.upper()


# --- construction ---


def test_empty_tools_has_no_categories() -> None:
    u = UnifiedTools()
    assert u.functions == []
    assert u.knowledge == []
    assert u.data_tables == []
    assert u.mcp_servers == []


def test_construction_with_all_categories() -> None:
    u = UnifiedTools(
        functions=[_example_func],
        knowledge=["./policies.pdf"],
        data_tables=[DataTable(name="t")],
        mcp_servers=["https://mcp.example.com"],
    )
    assert len(u.functions) == 1
    assert u.knowledge == ["./policies.pdf"]
    assert u.data_tables[0].name == "t"
    assert u.mcp_servers == ["https://mcp.example.com"]


# --- duplicate name validation ---


def test_duplicate_function_names_raise() -> None:
    with pytest.raises(ValueError, match="Duplicate tool name"):
        UnifiedTools(functions=[_example_func, _example_func])


def test_duplicate_data_table_names_raise() -> None:
    with pytest.raises(ValueError, match=r"Duplicate tool name.*query_x"):
        UnifiedTools(data_tables=[DataTable(name="x"), DataTable(name="x")])


def test_function_and_data_table_name_collision_raises() -> None:
    """A function named query_products would collide with a data table 'products'."""

    @function_tool(name_override="query_products")
    def fn() -> str:
        """Pretend collision."""
        return ""

    with pytest.raises(ValueError, match="Duplicate tool name"):
        UnifiedTools(functions=[fn], data_tables=[DataTable(name="products")])


# --- to_realtime_tools ---


def test_to_realtime_tools_passes_functions_through() -> None:
    u = UnifiedTools(functions=[_example_func, _another_func])
    tools = u.to_realtime_tools()
    assert tools == [_example_func, _another_func]


def test_to_realtime_tools_with_data_tables() -> None:
    u = UnifiedTools(data_tables=[DataTable(name="customers"), DataTable(name="orders")])
    tools = u.to_realtime_tools()
    assert len(tools) == 2
    names = {t.name for t in tools}
    assert names == {"query_customers", "query_orders"}


def test_to_realtime_tools_with_knowledge_uses_injected_embedder() -> None:
    async def fake_embed(text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    u = UnifiedTools(knowledge=["./doc.pdf"])
    tools = u.to_realtime_tools(embedder=fake_embed)
    assert len(tools) == 1
    assert tools[0].name == "search_knowledge"


def test_to_realtime_tools_knowledge_without_api_key_or_embedder_raises() -> None:
    u = UnifiedTools(knowledge=["./doc.pdf"])
    with pytest.raises(ValueError, match=r"api_key.*embedder"):
        u.to_realtime_tools()


def test_to_realtime_tools_mixes_all_categories() -> None:
    async def fake_embed(text: str) -> list[float]:
        return [0.1]

    u = UnifiedTools(
        functions=[_example_func],
        knowledge=["./doc.pdf"],
        data_tables=[DataTable(name="customers")],
    )
    tools = u.to_realtime_tools(embedder=fake_embed)
    assert len(tools) == 3
    # Order: functions first, then knowledge, then data tables.
    assert tools[0] is _example_func
    assert tools[1].name == "search_knowledge"
    assert tools[2].name == "query_customers"


# --- to_mcp_servers ---


def test_to_mcp_servers_promotes_strings() -> None:
    u = UnifiedTools(mcp_servers=["https://a.example.com", "https://b.example.com"])
    servers = u.to_mcp_servers()
    assert len(servers) == 2
    assert all(isinstance(s, MCPServerStreamableHttp) for s in servers)


def test_to_mcp_servers_accepts_specs() -> None:
    u = UnifiedTools(
        mcp_servers=[MCPServerSpec(url="https://x.example.com", headers={"Auth": "Bearer"})]
    )
    servers = u.to_mcp_servers()
    assert len(servers) == 1
    assert isinstance(servers[0], MCPServerStreamableHttp)


def test_to_mcp_servers_empty() -> None:
    assert UnifiedTools().to_mcp_servers() == []
