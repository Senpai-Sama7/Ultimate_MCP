"""Integration tests for Phase 1 features in enhanced_server."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from mcp_server.auth import Role


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j client."""
    client = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.execute_write = AsyncMock()
    client.execute_read = AsyncMock(return_value=[])
    return client


@pytest.fixture
def test_app(mock_neo4j):
    """Create test app with mocked dependencies."""
    with patch("mcp_server.enhanced_server.neo4j_client", mock_neo4j):
        with patch("mcp_server.enhanced_server.config") as mock_config:
            # Setup mock config
            mock_config.database.uri = "bolt://localhost:7687"
            mock_config.database.user = "neo4j"
            mock_config.database.password = "test"
            mock_config.database.database = "neo4j"
            mock_config.security.secret_key = "test-secret-key"
            mock_config.security.encryption_key = None
            mock_config.server.allowed_origins = ["*"]
            mock_config.server.allowed_methods = ["*"]
            mock_config.server.allowed_headers = ["*"]
            mock_config.is_production = False
            mock_config.environment = "test"
            mock_config.monitoring.log_format = "console"
            mock_config.monitoring.log_level = "info"
            mock_config.security.rate_limit_requests_per_minute = 60
            mock_config.security.rate_limit_requests_per_hour = 1000
            mock_config.security.rate_limit_requests_per_day = 10000
            
            from mcp_server.enhanced_server import app
            
            with TestClient(app) as client:
                yield client


def test_status_endpoint_includes_phase1_features(test_app):
    """Test that status endpoint shows Phase 1 features."""
    response = test_app.get("/status")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "security" in data
    security = data["security"]
    
    # Check Phase 1 features are reported
    assert "rbac" in security
    assert "audit_logging" in security


def test_assign_role_requires_admin_permission(test_app):
    """Test that role assignment requires admin permission."""
    # This should fail with 401/403 without proper auth
    response = test_app.post(
        "/api/v1/users/test-user/roles",
        json={"role": "developer"},
    )
    
    # Should be unauthorized or forbidden
    assert response.status_code in [401, 403]


def test_get_user_roles_requires_admin_permission(test_app):
    """Test that getting user roles requires admin permission."""
    response = test_app.get("/api/v1/users/test-user/roles")
    
    # Should be unauthorized or forbidden
    assert response.status_code in [401, 403]


def test_audit_log_query_requires_admin_permission(test_app):
    """Test that audit log query requires admin permission."""
    response = test_app.get("/api/v1/audit")
    
    # Should be unauthorized or forbidden
    assert response.status_code in [401, 403]


def test_execute_code_requires_execute_permission(test_app):
    """Test that code execution requires execute permission."""
    response = test_app.post(
        "/api/v1/execute",
        json={
            "code": "print('test')",
            "language": "python",
        },
    )
    
    # Should be unauthorized or forbidden without proper role
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_integration_with_jwt_and_rbac():
    """Test JWT and RBAC integration."""
    from mcp_server.auth import JWTHandler, Permission, RBACManager
    
    # Create handlers
    jwt_handler = JWTHandler(secret_key="test-secret")
    rbac_manager = RBACManager(neo4j_client=None)
    
    # Create token for developer
    token = jwt_handler.create_token(
        user_id="test-user",
        roles=[Role.DEVELOPER],
    )
    
    # Extract roles
    roles = jwt_handler.extract_roles(token)
    assert Role.DEVELOPER in roles
    
    # Check permissions
    assert rbac_manager.check_permission(roles, Permission("tools", "execute"))
    assert not rbac_manager.check_permission(roles, Permission("system", "admin"))


@pytest.mark.asyncio
async def test_audit_logging_integration():
    """Test audit logging integration."""
    from mcp_server.audit import AuditLogger
    
    # Create mock client
    mock_client = AsyncMock()
    mock_client.execute_write = AsyncMock()
    
    audit_logger = AuditLogger(neo4j_client=mock_client)
    
    # Test logging
    await audit_logger.log_authentication(
        success=True,
        user_id="test-user",
        ip_address="127.0.0.1",
    )
    
    # Verify write was called
    assert mock_client.execute_write.called
