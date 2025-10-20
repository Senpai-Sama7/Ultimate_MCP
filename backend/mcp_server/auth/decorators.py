"""Authentication and authorization decorators."""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException, Request, status

from .rbac import Permission


def require_permission(resource: str, action: str) -> Callable:
    """Decorator to require specific permission.

    Args:
        resource: Resource name
        action: Action name

    Returns:
        Decorator function
    """
    required_permission = Permission(resource, action)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract request from args/kwargs
            request: Request | None = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get("request")

            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found",
                )

            # Get security context from request state
            security_context = getattr(request.state, "security_context", None)
            if not security_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Check permission
            rbac_manager = getattr(request.app.state, "rbac_manager", None)
            if not rbac_manager:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="RBAC manager not initialized",
                )

            roles = getattr(security_context, "roles", [])
            if not roles:
                roles = []  # Default to no roles

            if not rbac_manager.check_permission(roles, required_permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {required_permission}",
                )

            return await func(*args, **kwargs)

        wrapper.__signature__ = inspect.signature(func)

        return wrapper

    return decorator
