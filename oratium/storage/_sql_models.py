"""SQLAlchemy declarative models. Internal — adopters use the public stores."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from oratium.tenant import Tenant, TenantAgentConfig


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for the tenants table."""


class TenantRow(Base):
    """ORM mapping for the ``tenants`` table.

    ``agent_config`` is JSON so Phase 4 can add tool / knowledge / MCP
    sub-models without a schema migration. We never query *into* the JSON;
    lookup is by ``id`` or ``twilio_number`` only, both of which have
    indexes.
    """

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    twilio_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    agent_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    def to_pydantic(self) -> Tenant:
        return Tenant(
            id=self.id,
            twilio_number=self.twilio_number,
            agent=TenantAgentConfig.model_validate(self.agent_config),
        )

    @classmethod
    def from_pydantic(cls, tenant: Tenant) -> TenantRow:
        return cls(
            id=tenant.id,
            twilio_number=tenant.twilio_number,
            agent_config=tenant.agent.model_dump(),
        )
