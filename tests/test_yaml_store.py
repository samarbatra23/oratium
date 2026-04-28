from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from oratium.storage.yaml_store import YAMLTenantStore

VALID_YAML = """\
tenants:
  - id: support
    twilio_number: "+15555550100"
    agent:
      name: Support
      instructions: |
        You are a support agent.
      voice: alloy
      model: gpt-realtime
  - id: sales
    twilio_number: "+15555550200"
    agent:
      name: Sales
      voice: verse
      model: gpt-realtime
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "tenants.yaml"
    path.write_text(body)
    return path


def test_load_two_tenants(tmp_path: Path) -> None:
    store = YAMLTenantStore(_write(tmp_path, VALID_YAML))
    # Sync interface used in init; async tests below cover the public API.
    assert "support" in store._by_id
    assert "+15555550200" in store._by_number


async def test_lookup_by_twilio_number(tmp_path: Path) -> None:
    store = YAMLTenantStore(_write(tmp_path, VALID_YAML))
    tenant = await store.get_by_twilio_number("+15555550100")
    assert tenant is not None
    assert tenant.id == "support"
    assert tenant.agent.name == "Support"


async def test_lookup_by_id(tmp_path: Path) -> None:
    store = YAMLTenantStore(_write(tmp_path, VALID_YAML))
    tenant = await store.get_by_id("sales")
    assert tenant is not None
    assert tenant.twilio_number == "+15555550200"
    assert tenant.agent.voice == "verse"


async def test_lookup_misses(tmp_path: Path) -> None:
    store = YAMLTenantStore(_write(tmp_path, VALID_YAML))
    assert await store.get_by_twilio_number("+19999999999") is None
    assert await store.get_by_id("ghost") is None


async def test_list_all_returns_every_tenant(tmp_path: Path) -> None:
    store = YAMLTenantStore(_write(tmp_path, VALID_YAML))
    tenants = await store.list_all()
    assert len(tenants) == 2
    assert {t.id for t in tenants} == {"support", "sales"}


def test_duplicate_ids_raise(tmp_path: Path) -> None:
    body = """\
tenants:
  - id: dup
    twilio_number: "+15555550100"
    agent: {name: A}
  - id: dup
    twilio_number: "+15555550200"
    agent: {name: B}
"""
    with pytest.raises(ValueError, match="Duplicate tenant id: dup"):
        YAMLTenantStore(_write(tmp_path, body))


def test_duplicate_numbers_raise(tmp_path: Path) -> None:
    body = """\
tenants:
  - id: a
    twilio_number: "+15555550100"
    agent: {name: A}
  - id: b
    twilio_number: "+15555550100"
    agent: {name: B}
"""
    with pytest.raises(ValueError, match="Duplicate Twilio number"):
        YAMLTenantStore(_write(tmp_path, body))


def test_invalid_e164_number_raises(tmp_path: Path) -> None:
    body = """\
tenants:
  - id: bad
    twilio_number: "5555550100"
    agent: {name: B}
"""
    with pytest.raises(ValidationError):
        YAMLTenantStore(_write(tmp_path, body))


def test_empty_file_loads_no_tenants(tmp_path: Path) -> None:
    store = YAMLTenantStore(_write(tmp_path, ""))
    assert store._by_id == {}


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    body = "- not\n- a\n- mapping\n"
    with pytest.raises(ValueError, match="top-level must be a mapping"):
        YAMLTenantStore(_write(tmp_path, body))


def test_tenants_field_must_be_list(tmp_path: Path) -> None:
    body = "tenants: not-a-list\n"
    with pytest.raises(ValueError, match="'tenants' must be a list"):
        YAMLTenantStore(_write(tmp_path, body))
