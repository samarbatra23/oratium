"""Tenant configuration model — the shape that flows from YAML / DB into the runtime."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from oratium.agent import DEFAULT_MODEL, DEFAULT_VOICE, Agent
from oratium.tools.data_tables import DataTable
from oratium.tools.functions import resolve_function_path
from oratium.tools.mcp import MCPServerSpec
from oratium.tools.unified import UnifiedTools


class TenantToolsConfig(BaseModel):
    """Declarative tool configuration loaded from YAML / DB.

    ``functions`` are import paths (e.g. ``"myapp.tools.transfer_to_human"``)
    because Python callables can't live in YAML. The other categories are
    config-only. :meth:`resolve` returns a :class:`UnifiedTools` instance
    ready for the runtime agent.
    """

    model_config = ConfigDict(extra="forbid")

    functions: list[str] = Field(default_factory=list)
    knowledge: list[str] = Field(default_factory=list)
    data_tables: list[DataTable] = Field(default_factory=list)
    mcp_servers: list[str | MCPServerSpec] = Field(default_factory=list)

    def resolve(self) -> UnifiedTools:
        """Resolve import paths and build a :class:`UnifiedTools` instance."""
        return UnifiedTools(
            functions=[resolve_function_path(p) for p in self.functions],
            knowledge=list(self.knowledge),
            data_tables=list(self.data_tables),
            mcp_servers=list(self.mcp_servers),
        )


class TenantAgentConfig(BaseModel):
    """Per-tenant agent definition.

    Mirrors the public knobs of :class:`oratium.Agent`. Stored as JSON in
    SQL backends (one row per tenant), so this model evolves freely
    without schema migrations as Phase 4 adds tools / knowledge / MCP
    sub-models.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    instructions: str | None = None
    voice: str = DEFAULT_VOICE
    model: str = DEFAULT_MODEL
    tools: TenantToolsConfig | None = None


class TenantSecrets(BaseModel):
    """Per-tenant secrets — encrypted at rest in SQL backends.

    Closed model rather than open dict so every secret type lands as an
    explicit, type-checked field. Phase 4 will add tool credentials.
    """

    model_config = ConfigDict(extra="forbid")

    openai_api_key: str | None = Field(
        default=None,
        description="Per-tenant OpenAI API key, overrides the deployment-wide key.",
    )


class Tenant(BaseModel):
    """A multi-tenant configuration entry."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Stable tenant identifier")
    twilio_number: str = Field(
        pattern=r"^\+[1-9]\d{1,14}$",
        description="E.164-formatted Twilio number, e.g. +15555550100",
    )
    agent: TenantAgentConfig
    secrets: TenantSecrets | None = None

    def to_runtime_agent(self) -> Agent:
        """Build the runtime :class:`oratium.Agent` from this tenant's config."""
        tools_payload: list[Any] | UnifiedTools = (
            self.agent.tools.resolve() if self.agent.tools else []
        )
        return Agent(
            name=self.agent.name,
            instructions=self.agent.instructions,
            voice=self.agent.voice,
            model=self.agent.model,
            tools=tools_payload,
        )

    def resolve_api_key(self, fallback: str) -> str:
        """Pick the OpenAI API key for this tenant's calls.

        Per-tenant ``secrets.openai_api_key`` wins over the
        deployment-wide ``fallback``.
        """
        if self.secrets is not None and self.secrets.openai_api_key:
            return self.secrets.openai_api_key
        return fallback
