"""Tenant configuration model — the shape that flows from YAML / DB into the runtime."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from oratium.agent import DEFAULT_MODEL, DEFAULT_VOICE, Agent


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


class Tenant(BaseModel):
    """A multi-tenant configuration entry."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Stable tenant identifier")
    twilio_number: str = Field(
        pattern=r"^\+[1-9]\d{1,14}$",
        description="E.164-formatted Twilio number, e.g. +15555550100",
    )
    agent: TenantAgentConfig

    def to_runtime_agent(self) -> Agent:
        """Build the runtime :class:`oratium.Agent` from this tenant's config."""
        return Agent(
            name=self.agent.name,
            instructions=self.agent.instructions,
            voice=self.agent.voice,
            model=self.agent.model,
        )
