"""Role-Based Access Control (RBAC) implementation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Role(Enum):
    """User roles."""

    VIEWER = "viewer"
    DEVELOPER = "developer"
    ADMIN = "admin"


@dataclass(frozen=True)
class Permission:
    """Permission definition."""

    resource: str  # 'tools', 'graph', 'system'
    action: str  # 'read', 'write', 'execute', 'delete', 'admin'

    def __str__(self) -> str:
        """String representation."""
        return f"{self.resource}:{self.action}"


# Role → Permissions mapping
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.VIEWER: [
        Permission("tools", "read"),
        Permission("tools", "lint"),
        Permission("graph", "query"),
    ],
    Role.DEVELOPER: [
        # Inherits all viewer permissions
        Permission("tools", "read"),
        Permission("tools", "lint"),
        Permission("graph", "query"),
        # Additional developer permissions
        Permission("tools", "execute"),
        Permission("tools", "test"),
        Permission("tools", "generate"),
    ],
    Role.ADMIN: [
        # Inherits all developer permissions
        Permission("tools", "read"),
        Permission("tools", "lint"),
        Permission("graph", "query"),
        Permission("tools", "execute"),
        Permission("tools", "test"),
        Permission("tools", "generate"),
        # Additional admin permissions
        Permission("graph", "upsert"),
        Permission("graph", "delete"),
        Permission("system", "admin"),
    ],
}


class RBACManager:
    """Role-Based Access Control manager."""

    def __init__(self, neo4j_client: Any = None):
        """Initialize RBAC manager.

        Args:
            neo4j_client: Optional Neo4j client for persistence
        """
        self.neo4j_client = neo4j_client

    def get_role_permissions(self, role: Role) -> list[Permission]:
        """Get all permissions for a role.

        Args:
            role: User role

        Returns:
            List of permissions
        """
        return ROLE_PERMISSIONS.get(role, [])

    def check_permission(self, roles: list[Role], required_permission: Permission) -> bool:
        """Check if user has required permission.

        Args:
            roles: User's roles
            required_permission: Permission to check

        Returns:
            True if user has permission
        """
        user_permissions = set()
        for role in roles:
            user_permissions.update(self.get_role_permissions(role))

        return required_permission in user_permissions

    async def assign_role(self, user_id: str, role: Role) -> None:
        """Assign role to user.

        Args:
            user_id: User identifier
            role: Role to assign
        """
        if not self.neo4j_client:
            return

        query = """
        MERGE (u:User {user_id: $user_id})
        MERGE (r:Role {name: $role})
        MERGE (u)-[:HAS_ROLE]->(r)
        """
        await self.neo4j_client.execute_write(query, {"user_id": user_id, "role": role.value})

    async def get_user_roles(self, user_id: str) -> list[Role]:
        """Get user's roles.

        Args:
            user_id: User identifier

        Returns:
            List of user's roles
        """
        if not self.neo4j_client:
            return [Role.VIEWER]  # Default role

        query = """
        MATCH (u:User {user_id: $user_id})-[:HAS_ROLE]->(r:Role)
        RETURN r.name AS role
        """
        results = await self.neo4j_client.execute_read(query, {"user_id": user_id})

        roles = []
        for result in results:
            try:
                roles.append(Role(result["role"]))
            except ValueError:
                pass  # Invalid role, skip

        return roles or [Role.VIEWER]  # Default to viewer if no roles found
