"""Data tables — in-memory rows the agent can query through a function tool."""

from __future__ import annotations

import json
from typing import Any

from agents import function_tool
from pydantic import BaseModel, ConfigDict, Field


class DataTable(BaseModel):
    """A named in-memory table the agent can filter by equality.

    Becomes a function tool ``query_<name>(filters: dict[str, str] | None)``
    at agent build time. Rows are arbitrary JSON-serializable dicts; v0
    supports equality filters only (``column == value``).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str = ""
    rows: list[dict[str, Any]] = Field(default_factory=list)


def make_query_function(table: DataTable) -> Any:
    """Build a ``function_tool``-wrapped callable that queries the table."""
    rows = list(table.rows)
    name = table.name
    description = (
        table.description
        or f"Query the {name} table. Pass column=value pairs in 'filters' to narrow the result;"
        " omit 'filters' to return every row."
    )

    async def _query(filters: dict[str, Any] | None = None) -> str:
        f = filters or {}
        matches = [row for row in rows if all(row.get(k) == v for k, v in f.items())]
        return json.dumps(matches, default=str)

    _query.__doc__ = description

    return function_tool(
        _query,
        name_override=f"query_{name}",
        description_override=description,
        # dict[str, Any] generates JSON schema with additionalProperties: True,
        # which the SDK's strict mode rejects. We want arbitrary keys here
        # (column names are tenant-defined), so disable strict for this tool.
        strict_mode=False,
    )
