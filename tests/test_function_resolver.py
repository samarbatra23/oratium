from __future__ import annotations

import pytest

from oratium.tools.functions import resolve_function_path


def test_resolves_existing_callable() -> None:
    # json.dumps is a stable, well-known callable.
    fn = resolve_function_path("json.dumps")
    assert callable(fn)
    assert fn({"x": 1}) == '{"x": 1}'


def test_resolves_nested_module_path() -> None:
    fn = resolve_function_path("os.path.join")
    assert callable(fn)
    assert fn("a", "b") == "a/b" or fn("a", "b") == "a\\b"


def test_rejects_path_without_module() -> None:
    with pytest.raises(ValueError, match="must include a module"):
        resolve_function_path("just_a_name")


def test_rejects_unknown_module() -> None:
    with pytest.raises(ValueError, match="Could not import module"):
        resolve_function_path("definitely_not_a_real_module.func")


def test_rejects_unknown_attribute() -> None:
    with pytest.raises(ValueError, match="has no attribute"):
        resolve_function_path("json.does_not_exist_xyz")
