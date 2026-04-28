"""Plain function tools — passthrough to ``agents.function_tool``.

Adopters typically pass ``@function_tool``-decorated callables directly to
:class:`oratium.UnifiedTools`. This module's only responsibility is
resolving import-path strings (used in YAML / DB tenant configs) into the
underlying callables at runtime.
"""

from __future__ import annotations

import importlib
from typing import Any


def resolve_function_path(path: str) -> Any:
    """Resolve ``"module.submodule.func_name"`` to the callable.

    Used by :class:`TenantToolsConfig` to lift function references out of
    YAML / DB into runtime callables. Raises :class:`ValueError` if the
    path is malformed or the attribute does not exist.
    """
    if "." not in path:
        raise ValueError(
            f"Function tool path must include a module: {path!r}. "
            "Example: 'mypackage.tools.transfer_to_human'"
        )
    module_path, _, func_name = path.rpartition(".")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ValueError(
            f"Could not import module {module_path!r} for function tool: {exc}"
        ) from exc
    func = getattr(module, func_name, None)
    if func is None:
        raise ValueError(
            f"Module {module_path!r} has no attribute {func_name!r}; "
            "check the function tool import path."
        )
    return func
