"""oratium — production-grade multi-tenant voice agent framework on the OpenAI Agents SDK."""

from oratium.agent import Agent
from oratium.app import OratiumApp
from oratium.storage import (
    PostgresTenantStore,
    SQLiteTenantStore,
    TenantStore,
    YAMLTenantStore,
)
from oratium.tenant import Tenant, TenantAgentConfig

__version__ = "0.0.1"

__all__ = [
    "Agent",
    "OratiumApp",
    "PostgresTenantStore",
    "SQLiteTenantStore",
    "Tenant",
    "TenantAgentConfig",
    "TenantStore",
    "YAMLTenantStore",
    "__version__",
]
