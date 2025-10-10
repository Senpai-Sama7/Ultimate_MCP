"""Tests for RBAC functionality."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mcp_server.auth.rbac import ROLE_PERMISSIONS, Permission, RBACManager, Role


@pytest.fixture
def mock_neo4j_client():
    """Create mock Neo4j client."""
    client = AsyncMock()
    client.execute_write = AsyncMock()
    client.execute_read = AsyncMock(return_value=[])
    return client


@pytest.fixture
def rbac_manager(mock_neo4j_client):
    """Create RBAC manager instance."""
    return RBACManager(neo4j_client=mock_neo4j_client)


def test_viewer_permissions():
    """Test viewer role has correct permissions."""
    rbac = RBACManager()

    # Viewer can lint
    assert rbac.check_permission([Role.VIEWER], Permission("tools", "lint"))

    # Viewer can query graph
    assert rbac.check_permission([Role.VIEWER], Permission("graph", "query"))

    # Viewer cannot execute
    assert not rbac.check_permission([Role.VIEWER], Permission("tools", "execute"))

    # Viewer cannot upsert graph
    assert not rbac.check_permission([Role.VIEWER], Permission("graph", "upsert"))


def test_developer_permissions():
    """Test developer role has correct permissions."""
    rbac = RBACManager()

    # Developer has viewer permissions
    assert rbac.check_permission([Role.DEVELOPER], Permission("tools", "lint"))
    assert rbac.check_permission([Role.DEVELOPER], Permission("graph", "query"))

    # Developer can execute
    assert rbac.check_permission([Role.DEVELOPER], Permission("tools", "execute"))

    # Developer can test
    assert rbac.check_permission([Role.DEVELOPER], Permission("tools", "test"))

    # Developer can generate
    assert rbac.check_permission([Role.DEVELOPER], Permission("tools", "generate"))

    # Developer cannot upsert graph
    assert not rbac.check_permission([Role.DEVELOPER], Permission("graph", "upsert"))

    # Developer cannot access system admin
    assert not rbac.check_permission([Role.DEVELOPER], Permission("system", "admin"))


def test_admin_permissions():
    """Test admin role has all permissions."""
    rbac = RBACManager()

    # Admin has developer permissions
    assert rbac.check_permission([Role.ADMIN], Permission("tools", "execute"))
    assert rbac.check_permission([Role.ADMIN], Permission("tools", "test"))

    # Admin can upsert graph
    assert rbac.check_permission([Role.ADMIN], Permission("graph", "upsert"))

    # Admin can delete graph
    assert rbac.check_permission([Role.ADMIN], Permission("graph", "delete"))

    # Admin can access system admin
    assert rbac.check_permission([Role.ADMIN], Permission("system", "admin"))


def test_multiple_roles():
    """Test user with multiple roles."""
    rbac = RBACManager()

    # User with both viewer and developer roles
    roles = [Role.VIEWER, Role.DEVELOPER]

    # Should have developer permissions
    assert rbac.check_permission(roles, Permission("tools", "execute"))


def test_no_roles():
    """Test user with no roles."""
    rbac = RBACManager()

    # No roles = no permissions
    assert not rbac.check_permission([], Permission("tools", "lint"))


def test_permission_string_representation():
    """Test permission string representation."""
    perm = Permission("tools", "execute")
    assert str(perm) == "tools:execute"


def test_role_permissions_mapping():
    """Test role permissions mapping is correct."""
    # Viewer should have 3 permissions
    assert len(ROLE_PERMISSIONS[Role.VIEWER]) == 3

    # Developer should have 6 permissions
    assert len(ROLE_PERMISSIONS[Role.DEVELOPER]) == 6

    # Admin should have 9 permissions
    assert len(ROLE_PERMISSIONS[Role.ADMIN]) == 9


def test_get_role_permissions():
    """Test getting permissions for a role."""
    rbac = RBACManager()

    viewer_perms = rbac.get_role_permissions(Role.VIEWER)
    assert len(viewer_perms) == 3
    assert Permission("tools", "lint") in viewer_perms

    developer_perms = rbac.get_role_permissions(Role.DEVELOPER)
    assert len(developer_perms) == 6
    assert Permission("tools", "execute") in developer_perms

    admin_perms = rbac.get_role_permissions(Role.ADMIN)
    assert len(admin_perms) == 9
    assert Permission("system", "admin") in admin_perms


@pytest.mark.asyncio
async def test_assign_role(rbac_manager, mock_neo4j_client):
    """Test assigning role to user."""
    await rbac_manager.assign_role("user-123", Role.DEVELOPER)

    # Verify Neo4j write was called
    assert mock_neo4j_client.execute_write.called
    call_args = mock_neo4j_client.execute_write.call_args
    query, parameters = call_args[0]

    assert "MERGE (u:User" in query
    assert "MERGE (r:Role" in query
    assert "HAS_ROLE" in query
    assert parameters["user_id"] == "user-123"
    assert parameters["role"] == "developer"


@pytest.mark.asyncio
async def test_get_user_roles(rbac_manager, mock_neo4j_client):
    """Test getting user roles."""
    # Mock Neo4j response
    mock_neo4j_client.execute_read.return_value = [{"role": "developer"}, {"role": "admin"}]

    roles = await rbac_manager.get_user_roles("user-123")

    assert len(roles) == 2
    assert Role.DEVELOPER in roles
    assert Role.ADMIN in roles


@pytest.mark.asyncio
async def test_get_user_roles_no_roles(rbac_manager, mock_neo4j_client):
    """Test getting user roles when user has no roles."""
    # Mock empty Neo4j response
    mock_neo4j_client.execute_read.return_value = []

    roles = await rbac_manager.get_user_roles("user-123")

    # Should default to viewer
    assert roles == [Role.VIEWER]


@pytest.mark.asyncio
async def test_get_user_roles_invalid_role(rbac_manager, mock_neo4j_client):
    """Test handling invalid role in database."""
    # Mock Neo4j response with invalid role
    mock_neo4j_client.execute_read.return_value = [
        {"role": "developer"},
        {"role": "invalid_role"},  # This should be skipped
    ]

    roles = await rbac_manager.get_user_roles("user-123")

    # Should only have developer role (invalid skipped)
    assert len(roles) == 1
    assert Role.DEVELOPER in roles


@pytest.mark.asyncio
async def test_rbac_manager_without_neo4j():
    """Test RBAC manager works without Neo4j client."""
    rbac = RBACManager(neo4j_client=None)

    # Should not raise errors
    await rbac.assign_role("user-123", Role.DEVELOPER)

    # Should return default role
    roles = await rbac.get_user_roles("user-123")
    assert roles == [Role.VIEWER]
