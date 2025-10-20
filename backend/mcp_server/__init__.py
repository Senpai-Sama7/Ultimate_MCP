"""Ultimate MCP backend package."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_SUBMODULE_ALIASES = {
    "enhanced_server": "mcp_server.enhanced_server",
}

__all__ = ["app", "settings"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        server = import_module("mcp_server.server")
        return getattr(server, name)
    if name in _SUBMODULE_ALIASES:
        return import_module(_SUBMODULE_ALIASES[name])
    raise AttributeError(f"module 'mcp_server' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
