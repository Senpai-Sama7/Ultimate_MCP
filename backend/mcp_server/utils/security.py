"""Compatibility shim for legacy security helpers.

This module re-exports the enhanced security utilities so existing imports
(`backend.mcp_server.utils.security`) continue to work while the codebase
standardises on `enhanced_security`.
"""

from __future__ import annotations

from .enhanced_security import SecurityViolationError, ensure_safe_python

__all__ = ["ensure_safe_python", "SecurityViolationError"]
