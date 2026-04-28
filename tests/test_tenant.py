from __future__ import annotations

import pytest
from pydantic import ValidationError

from oratium.agent import DEFAULT_MODEL, DEFAULT_VOICE, Agent
from oratium.tenant import Tenant, TenantAgentConfig, TenantSecrets


def test_tenant_minimal_construction() -> None:
    tenant = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(name="Hello"),
    )
    assert tenant.id == "t1"
    assert tenant.twilio_number == "+15555550100"
    assert tenant.agent.name == "Hello"
    assert tenant.agent.instructions is None
    assert tenant.agent.voice == DEFAULT_VOICE
    assert tenant.agent.model == DEFAULT_MODEL


def test_tenant_full_construction() -> None:
    tenant = Tenant(
        id="support",
        twilio_number="+18005551234",
        agent=TenantAgentConfig(
            name="Support",
            instructions="Be helpful",
            voice="verse",
            model="gpt-realtime-x",
        ),
    )
    assert tenant.agent.instructions == "Be helpful"
    assert tenant.agent.voice == "verse"
    assert tenant.agent.model == "gpt-realtime-x"


@pytest.mark.parametrize(
    "bad_number",
    [
        "5555550100",  # missing +
        "+1",  # too short
        "++15555550100",  # double plus
        "+0555550100",  # leading 0 after +
        "1-800-555-1234",  # formatted
        "",
    ],
)
def test_tenant_rejects_non_e164_numbers(bad_number: str) -> None:
    with pytest.raises(ValidationError):
        Tenant(
            id="t1",
            twilio_number=bad_number,
            agent=TenantAgentConfig(name="x"),
        )


def test_tenant_rejects_empty_id() -> None:
    with pytest.raises(ValidationError):
        Tenant(
            id="",
            twilio_number="+15555550100",
            agent=TenantAgentConfig(name="x"),
        )


def test_tenant_rejects_unknown_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        Tenant.model_validate(
            {
                "id": "t1",
                "twilio_number": "+15555550100",
                "agent": {"name": "x"},
                "unexpected": "field",
            }
        )


def test_tenant_agent_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TenantAgentConfig.model_validate({"name": "x", "unknown": "y"})


def test_tenant_agent_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        TenantAgentConfig(name="")


def test_to_runtime_agent_builds_oratium_agent() -> None:
    tenant = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(
            name="Hello",
            instructions="Greet warmly",
            voice="verse",
            model="custom-model",
        ),
    )
    agent = tenant.to_runtime_agent()
    assert isinstance(agent, Agent)
    assert agent.name == "Hello"
    assert agent.instructions == "Greet warmly"
    assert agent.voice == "verse"
    assert agent.model == "custom-model"


def test_tenant_round_trips_through_dict() -> None:
    original = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(name="x", instructions="y"),
    )
    restored = Tenant.model_validate(original.model_dump())
    assert restored == original


# --- TenantSecrets ---


def test_secrets_default_is_none() -> None:
    tenant = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(name="x"),
    )
    assert tenant.secrets is None


def test_secrets_with_openai_key() -> None:
    tenant = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(name="x"),
        secrets=TenantSecrets(openai_api_key="sk-tenant"),
    )
    assert tenant.secrets is not None
    assert tenant.secrets.openai_api_key == "sk-tenant"


def test_secrets_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TenantSecrets.model_validate({"openai_api_key": "sk-x", "secret_extra": "y"})


def test_resolve_api_key_uses_tenant_secret_when_set() -> None:
    tenant = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(name="x"),
        secrets=TenantSecrets(openai_api_key="sk-tenant"),
    )
    assert tenant.resolve_api_key("sk-fallback") == "sk-tenant"


def test_resolve_api_key_falls_back_when_no_secrets() -> None:
    tenant = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(name="x"),
    )
    assert tenant.resolve_api_key("sk-fallback") == "sk-fallback"


def test_resolve_api_key_falls_back_when_secrets_field_is_none() -> None:
    tenant = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(name="x"),
        secrets=TenantSecrets(),  # secrets present but openai_api_key=None
    )
    assert tenant.resolve_api_key("sk-fallback") == "sk-fallback"
