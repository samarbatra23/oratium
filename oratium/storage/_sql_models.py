"""SQLAlchemy declarative models. Internal — adopters use the public stores."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for the tenants table."""


class TenantRow(Base):
    """ORM mapping for the ``tenants`` table.

    ``agent_config`` is JSON so Phase 4 can add tool / knowledge / MCP
    sub-models without a schema migration. ``secrets_encrypted`` is a
    Fernet ciphertext over the JSON-serialized :class:`TenantSecrets`
    model — encryption is handled by the store, not by this row class.
    """

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    twilio_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    agent_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    secrets_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
