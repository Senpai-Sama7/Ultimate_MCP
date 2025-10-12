"""Tests for Neo4j index management."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from mcp_server.database.indexes import IndexManager


@pytest.fixture
def mock_neo4j_client():
    """Create mock Neo4j client."""
    client = AsyncMock()
    client.execute_write = AsyncMock()
    client.execute_read = AsyncMock(return_value=[])
    return client


@pytest.fixture
def index_manager(mock_neo4j_client):
    """Create index manager instance."""
    return IndexManager(mock_neo4j_client)


@pytest.mark.asyncio
async def test_create_all_indexes(index_manager, mock_neo4j_client):
    """Test creating all recommended indexes."""
    results = await index_manager.create_all_indexes()

    # Should have created multiple indexes
    assert len(results) > 0
    
    # All should succeed with mock
    assert all(results.values())
    
    # Verify Neo4j write calls were made
    assert mock_neo4j_client.execute_write.call_count == len(results)


@pytest.mark.asyncio
async def test_create_all_indexes_includes_audit_indexes(
    index_manager,
    mock_neo4j_client,
):
    """Test audit event indexes are created."""
    results = await index_manager.create_all_indexes()

    # Check for audit-related indexes
    assert "audit_event_type_timestamp" in results
    assert "audit_user_id" in results
    assert "audit_request_id" in results


@pytest.mark.asyncio
async def test_create_all_indexes_includes_result_indexes(
    index_manager,
    mock_neo4j_client,
):
    """Test execution result indexes are created."""
    results = await index_manager.create_all_indexes()

    # Check for result indexes
    assert "lint_result_hash" in results
    assert "execution_result_timestamp" in results
    assert "test_result_timestamp" in results


@pytest.mark.asyncio
async def test_create_all_indexes_includes_user_indexes(
    index_manager,
    mock_neo4j_client,
):
    """Test user management indexes are created."""
    results = await index_manager.create_all_indexes()

    # Check for user/role indexes
    assert "user_id" in results
    assert "role_name" in results


@pytest.mark.asyncio
async def test_create_all_indexes_handles_failures(index_manager, mock_neo4j_client):
    """Test graceful handling of index creation failures."""
    # Simulate failure for one index
    call_count = 0

    async def mock_write(query):
        nonlocal call_count
        call_count += 1
        if "audit_user_id" in query:
            raise Exception("Simulated failure")

    mock_neo4j_client.execute_write = mock_write

    results = await index_manager.create_all_indexes()

    # Should have attempted all indexes
    assert len(results) > 0
    
    # The failing index should be marked as failed
    assert results.get("audit_user_id") is False
    
    # Other indexes should succeed
    successful_indexes = [k for k, v in results.items() if v and k != "audit_user_id"]
    assert len(successful_indexes) > 0


@pytest.mark.asyncio
async def test_create_constraints(index_manager, mock_neo4j_client):
    """Test creating uniqueness constraints."""
    results = await index_manager.create_constraints()

    # Should have created multiple constraints
    assert len(results) > 0
    
    # All should succeed with mock
    assert all(results.values())
    
    # Verify Neo4j write calls were made
    assert mock_neo4j_client.execute_write.call_count == len(results)


@pytest.mark.asyncio
async def test_create_constraints_includes_uniqueness(
    index_manager,
    mock_neo4j_client,
):
    """Test uniqueness constraints are created."""
    results = await index_manager.create_constraints()

    # Check for uniqueness constraints
    assert "unique_audit_event_id" in results
    assert "unique_user_id" in results
    assert "unique_role_name" in results


@pytest.mark.asyncio
async def test_list_indexes(index_manager, mock_neo4j_client):
    """Test listing all indexes."""
    # Setup mock to return index data
    mock_indexes = [
        {"name": "audit_user_id", "type": "BTREE"},
        {"name": "lint_result_hash", "type": "BTREE"},
    ]
    mock_neo4j_client.execute_read = AsyncMock(return_value=mock_indexes)

    results = await index_manager.list_indexes()

    assert len(results) == 2
    assert results[0]["name"] == "audit_user_id"
    assert results[1]["name"] == "lint_result_hash"
    
    # Verify query was executed
    mock_neo4j_client.execute_read.assert_called_once()


@pytest.mark.asyncio
async def test_list_indexes_handles_errors(index_manager, mock_neo4j_client):
    """Test graceful handling of list indexes errors."""
    mock_neo4j_client.execute_read = AsyncMock(side_effect=Exception("DB error"))

    results = await index_manager.list_indexes()

    # Should return empty list on error
    assert results == []


@pytest.mark.asyncio
async def test_drop_index(index_manager, mock_neo4j_client):
    """Test dropping a specific index."""
    result = await index_manager.drop_index("audit_user_id")

    assert result is True
    
    # Verify Neo4j write was called with DROP statement
    mock_neo4j_client.execute_write.assert_called_once()
    call_args = mock_neo4j_client.execute_write.call_args[0][0]
    assert "DROP INDEX" in call_args
    assert "audit_user_id" in call_args


@pytest.mark.asyncio
async def test_drop_index_handles_errors(index_manager, mock_neo4j_client):
    """Test graceful handling of drop index errors."""
    mock_neo4j_client.execute_write = AsyncMock(side_effect=Exception("DB error"))

    result = await index_manager.drop_index("audit_user_id")

    assert result is False


@pytest.mark.asyncio
async def test_index_queries_use_if_not_exists(index_manager, mock_neo4j_client):
    """Test index creation uses IF NOT EXISTS for idempotency."""
    await index_manager.create_all_indexes()

    # Check that all queries include IF NOT EXISTS
    for call in mock_neo4j_client.execute_write.call_args_list:
        query = call[0][0]
        assert "IF NOT EXISTS" in query


@pytest.mark.asyncio
async def test_constraint_queries_use_if_not_exists(index_manager, mock_neo4j_client):
    """Test constraint creation uses IF NOT EXISTS for idempotency."""
    await index_manager.create_constraints()

    # Check that all queries include IF NOT EXISTS
    for call in mock_neo4j_client.execute_write.call_args_list:
        query = call[0][0]
        assert "IF NOT EXISTS" in query
