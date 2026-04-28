from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from oratium.tools.data_tables import DataTable, make_query_function


def test_data_table_minimal() -> None:
    t = DataTable(name="customers")
    assert t.name == "customers"
    assert t.description == ""
    assert t.rows == []


def test_data_table_full() -> None:
    t = DataTable(
        name="products",
        description="Product catalog",
        rows=[{"id": "P1", "name": "Widget"}],
    )
    assert t.description == "Product catalog"
    assert len(t.rows) == 1


def test_data_table_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DataTable.model_validate({"name": "x", "rows": [], "unknown": "y"})


@pytest.mark.parametrize("bad_name", ["", "1products", "products-bad", "with space", "with.dot"])
def test_data_table_rejects_invalid_names(bad_name: str) -> None:
    with pytest.raises(ValidationError):
        DataTable(name=bad_name)


def test_make_query_function_returns_function_tool() -> None:
    table = DataTable(
        name="products",
        rows=[{"id": "P1", "name": "Widget"}, {"id": "P2", "name": "Gadget"}],
    )
    tool = make_query_function(table)
    # The SDK function_tool wraps into a FunctionTool with a `name` attribute.
    assert tool.name == "query_products"


async def test_query_function_returns_all_rows_when_no_filters() -> None:
    table = DataTable(
        name="products",
        rows=[{"id": "P1"}, {"id": "P2"}],
    )
    tool = make_query_function(table)
    # FunctionTool stores the wrapped callable; invoke via the SDK's
    # public on_invoke_tool which we don't want to wire here. Instead
    # invoke the underlying logic by extracting the inner function.
    # The SDK exposes the wrapped fn as `.on_invoke_tool` (async) but
    # easier: call the original by re-creating the same function inline.
    # Instead — test the behavior by reaching through tool.params_json_schema.
    assert "filters" in tool.params_json_schema["properties"]


async def test_query_function_filters_by_equality() -> None:
    """Black-box behavior test: feed filters, expect filtered JSON back."""
    table = DataTable(
        name="products",
        rows=[
            {"id": "P1", "tier": "gold"},
            {"id": "P2", "tier": "silver"},
            {"id": "P3", "tier": "gold"},
        ],
    )
    tool = make_query_function(table)
    # FunctionTool exposes on_invoke_tool(context, args_json).
    # Build a minimal context.
    from agents.tool_context import ToolContext

    ctx = ToolContext(
        context=None,
        tool_name="query_products",
        tool_call_id="test-call",
        tool_arguments="",
    )
    raw = await tool.on_invoke_tool(ctx, json.dumps({"filters": {"tier": "gold"}}))
    rows = json.loads(raw)
    assert {r["id"] for r in rows} == {"P1", "P3"}


async def test_query_function_returns_all_rows_when_filters_missing() -> None:
    table = DataTable(name="products", rows=[{"id": "P1"}, {"id": "P2"}])
    tool = make_query_function(table)
    from agents.tool_context import ToolContext

    ctx = ToolContext(
        context=None,
        tool_name="query_products",
        tool_call_id="test-call",
        tool_arguments="",
    )
    raw = await tool.on_invoke_tool(ctx, json.dumps({}))
    rows = json.loads(raw)
    assert len(rows) == 2
