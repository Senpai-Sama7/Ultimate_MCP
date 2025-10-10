"""Tests for audit logging functionality."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from mcp_server.audit.logger import AuditEventType, AuditLogger


@pytest.fixture
def mock_neo4j_client():
    """Create mock Neo4j client."""
    client = AsyncMock()
    client.execute_write = AsyncMock()
    client.execute_read = AsyncMock(return_value=[])
    return client


@pytest.fixture
def audit_logger(mock_neo4j_client):
    """Create audit logger instance."""
    return AuditLogger(neo4j_client=mock_neo4j_client)


@pytest.mark.asyncio
async def test_log_authentication_success(audit_logger, mock_neo4j_client):
    """Test logging successful authentication."""
    await audit_logger.log_authentication(
        success=True,
        user_id="user-123",
        ip_address="192.168.1.100",
        user_agent="TestClient/1.0",
        request_id="req-456",
    )

    # Verify Neo4j write was called
    assert mock_neo4j_client.execute_write.called
    call_args = mock_neo4j_client.execute_write.call_args
    query, parameters = call_args[0]

    assert "CREATE (e:AuditEvent" in query
    assert parameters["event_type"] == "auth_success"
    assert parameters["user_id"] == "user-123"
    assert parameters["success"] is True


@pytest.mark.asyncio
async def test_log_authentication_failure(audit_logger, mock_neo4j_client):
    """Test logging failed authentication."""
    await audit_logger.log_authentication(
        success=False,
        ip_address="192.168.1.100",
        error_message="Invalid token",
    )

    call_args = mock_neo4j_client.execute_write.call_args
    _, parameters = call_args[0]

    assert parameters["event_type"] == "auth_failure"
    assert parameters["success"] is False
    assert parameters["error_message"] == "Invalid token"


@pytest.mark.asyncio
async def test_log_authorization_granted(audit_logger, mock_neo4j_client):
    """Test logging authorization grant."""
    await audit_logger.log_authorization(
        user_id="user-123",
        resource="code_execution",
        action="execute",
        granted=True,
        ip_address="192.168.1.100",
        details={"language": "python"},
    )

    call_args = mock_neo4j_client.execute_write.call_args
    _, parameters = call_args[0]

    assert parameters["event_type"] == "authz_granted"
    assert parameters["user_id"] == "user-123"
    assert parameters["resource"] == "code_execution"
    assert parameters["action"] == "execute"
    assert parameters["success"] is True


@pytest.mark.asyncio
async def test_log_authorization_denied(audit_logger, mock_neo4j_client):
    """Test logging authorization denial."""
    await audit_logger.log_authorization(
        user_id="user-123",
        resource="admin_panel",
        action="access",
        granted=False,
    )

    call_args = mock_neo4j_client.execute_write.call_args
    _, parameters = call_args[0]

    assert parameters["event_type"] == "authz_denied"
    assert parameters["success"] is False


@pytest.mark.asyncio
async def test_log_code_execution(audit_logger, mock_neo4j_client):
    """Test logging code execution."""
    await audit_logger.log_code_execution(
        user_id="user-123",
        code_hash="abc123",
        language="python",
        success=True,
        duration_ms=150.5,
        ip_address="192.168.1.100",
    )

    call_args = mock_neo4j_client.execute_write.call_args
    _, parameters = call_args[0]

    assert parameters["event_type"] == "code_execution"
    assert parameters["duration_ms"] == 150.5
    assert parameters["details"]["code_hash"] == "abc123"
    assert parameters["details"]["language"] == "python"


@pytest.mark.asyncio
async def test_log_security_violation(audit_logger, mock_neo4j_client):
    """Test logging security violation."""
    await audit_logger.log_security_violation(
        user_id="user-123",
        violation_type="injection_attempt",
        details={"code": "os.system('rm -rf /')"},
        ip_address="192.168.1.100",
    )

    call_args = mock_neo4j_client.execute_write.call_args
    _, parameters = call_args[0]

    assert parameters["event_type"] == "security_violation"
    assert parameters["action"] == "injection_attempt"
    assert parameters["success"] is False


@pytest.mark.asyncio
async def test_query_audit_log_no_filters(audit_logger, mock_neo4j_client):
    """Test querying audit log without filters."""
    await audit_logger.query_audit_log()

    assert mock_neo4j_client.execute_read.called
    call_args = mock_neo4j_client.execute_read.call_args
    query, parameters = call_args[0]

    assert "MATCH (e:AuditEvent)" in query
    assert "WHERE true" in query
    assert parameters["limit"] == 100


@pytest.mark.asyncio
async def test_query_audit_log_with_filters(audit_logger, mock_neo4j_client):
    """Test querying audit log with filters."""
    start_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2025, 12, 31, tzinfo=timezone.utc)

    await audit_logger.query_audit_log(
        event_type=AuditEventType.AUTH_SUCCESS,
        user_id="user-123",
        start_time=start_time,
        end_time=end_time,
        limit=50,
    )

    call_args = mock_neo4j_client.execute_read.call_args
    query, parameters = call_args[0]

    assert "e.event_type = $event_type" in query
    assert "e.user_id = $user_id" in query
    assert "e.timestamp >= datetime($start_time)" in query
    assert "e.timestamp <= datetime($end_time)" in query
    assert parameters["event_type"] == "auth_success"
    assert parameters["user_id"] == "user-123"
    assert parameters["limit"] == 50


@pytest.mark.asyncio
async def test_audit_logger_without_neo4j():
    """Test audit logger works without Neo4j client."""
    logger = AuditLogger(neo4j_client=None)

    # Should not raise errors
    await logger.log_authentication(success=True, user_id="user-123")

    # Query should return empty list
    results = await logger.query_audit_log()
    assert results == []


@pytest.mark.asyncio
async def test_audit_event_persistence_failure(audit_logger, mock_neo4j_client, caplog):
    """Test handling of Neo4j persistence failures."""
    mock_neo4j_client.execute_write.side_effect = Exception("Connection failed")

    # Should not raise exception, but log error
    await audit_logger.log_authentication(success=True, user_id="user-123")

    # Check that error was logged
    assert "Failed to persist audit event to Neo4j" in caplog.text
