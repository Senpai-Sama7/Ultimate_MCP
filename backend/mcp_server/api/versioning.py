"""API versioning strategy implementation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.routing import APIRoute
from pydantic import BaseModel


class APIVersion(str, Enum):
    """Supported API versions."""
    V1 = "v1"
    V2 = "v2"


class VersionedResponse(BaseModel):
    """Base response with version information."""
    api_version: str
    data: Any
    deprecated: Optional[bool] = None
    migration_guide: Optional[str] = None


class APIVersioning:
    """API versioning manager."""
    
    def __init__(self, default_version: APIVersion = APIVersion.V1):
        self.default_version = default_version
        self.routers: dict[APIVersion, APIRouter] = {}
        
        # Initialize routers for each version
        for version in APIVersion:
            self.routers[version] = APIRouter(
                prefix=f"/api/{version.value}",
                tags=[f"API {version.value.upper()}"]
            )
    
    def get_router(self, version: APIVersion) -> APIRouter:
        """Get router for specific API version."""
        return self.routers[version]
    
    def extract_version(self, request: Request) -> APIVersion:
        """Extract API version from request."""
        # Try path first (/api/v1/...)
        path_parts = request.url.path.split("/")
        if len(path_parts) >= 3 and path_parts[1] == "api":
            version_str = path_parts[2]
            try:
                return APIVersion(version_str)
            except ValueError:
                pass
        
        # Try Accept header (Accept: application/vnd.ultimate-mcp.v2+json)
        accept_header = request.headers.get("accept", "")
        if "vnd.ultimate-mcp.v2" in accept_header:
            return APIVersion.V2
        elif "vnd.ultimate-mcp.v1" in accept_header:
            return APIVersion.V1
        
        # Try custom header
        version_header = request.headers.get("X-API-Version")
        if version_header:
            try:
                return APIVersion(version_header)
            except ValueError:
                pass
        
        return self.default_version
    
    def versioned_endpoint(
        self,
        versions: list[APIVersion],
        deprecated_versions: Optional[list[APIVersion]] = None,
    ):
        """Decorator to create versioned endpoints."""
        deprecated_versions = deprecated_versions or []
        
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                # This will be handled by the router
                return func(*args, **kwargs)
            
            # Add endpoint to specified version routers
            for version in versions:
                router = self.routers[version]
                is_deprecated = version in deprecated_versions
                
                # Modify the function to add version info
                async def versioned_func(*args, **kwargs):
                    result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                    
                    if isinstance(result, dict):
                        return VersionedResponse(
                            api_version=version.value,
                            data=result,
                            deprecated=is_deprecated,
                            migration_guide=f"https://docs.ultimate-mcp.com/migration/{version.value}" if is_deprecated else None
                        )
                    return result
                
                # Register with router
                router.add_api_route(
                    path=func.__name__.replace("_", "-"),
                    endpoint=versioned_func,
                    methods=["POST"],
                    response_model=VersionedResponse if not is_deprecated else None,
                    deprecated=is_deprecated,
                )
            
            return wrapper
        return decorator


# Global versioning instance
_versioning: Optional[APIVersioning] = None


def get_versioning() -> APIVersioning:
    """Get global versioning instance."""
    global _versioning
    if _versioning is None:
        _versioning = APIVersioning()
    return _versioning


def init_versioning(default_version: APIVersion = APIVersion.V1) -> APIVersioning:
    """Initialize global versioning."""
    global _versioning
    _versioning = APIVersioning(default_version)
    return _versioning


# Convenience decorators
def v1_endpoint(func):
    """Mark endpoint as V1 only."""
    return get_versioning().versioned_endpoint([APIVersion.V1])(func)


def v2_endpoint(func):
    """Mark endpoint as V2 only."""
    return get_versioning().versioned_endpoint([APIVersion.V2])(func)


def v1_v2_endpoint(func):
    """Mark endpoint as available in both V1 and V2."""
    return get_versioning().versioned_endpoint([APIVersion.V1, APIVersion.V2])(func)


def deprecated_v1_endpoint(func):
    """Mark V1 endpoint as deprecated, available in V2."""
    return get_versioning().versioned_endpoint(
        [APIVersion.V1, APIVersion.V2],
        deprecated_versions=[APIVersion.V1]
    )(func)
