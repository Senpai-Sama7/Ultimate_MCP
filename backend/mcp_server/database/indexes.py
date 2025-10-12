"""Neo4j index management for performance optimization."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class IndexManager:
    """Manages Neo4j indexes for optimal query performance."""

    def __init__(self, client: Neo4jClient):
        """Initialize index manager.
        
        Args:
            client: Neo4j client instance
        """
        self.client = client

    async def create_all_indexes(self) -> dict[str, bool]:
        """Create all recommended indexes for the platform.
        
        Returns:
            Dictionary mapping index name to creation success status
        """
        indexes = {
            # Performance indexes for audit events
            "audit_event_type_timestamp": """
                CREATE INDEX audit_event_type_timestamp IF NOT EXISTS
                FOR (e:AuditEvent) ON (e.event_type, e.timestamp)
            """,
            "audit_user_id": """
                CREATE INDEX audit_user_id IF NOT EXISTS
                FOR (e:AuditEvent) ON (e.user_id)
            """,
            "audit_request_id": """
                CREATE INDEX audit_request_id IF NOT EXISTS
                FOR (e:AuditEvent) ON (e.request_id)
            """,
            
            # Performance indexes for execution results
            "lint_result_hash": """
                CREATE INDEX lint_result_hash IF NOT EXISTS
                FOR (n:LintResult) ON (n.code_hash)
            """,
            "execution_result_timestamp": """
                CREATE INDEX execution_result_timestamp IF NOT EXISTS
                FOR (n:ExecutionResult) ON (n.timestamp)
            """,
            "test_result_timestamp": """
                CREATE INDEX test_result_timestamp IF NOT EXISTS
                FOR (n:TestResult) ON (n.timestamp)
            """,
            
            # Performance indexes for graph operations
            "service_name": """
                CREATE INDEX service_name IF NOT EXISTS
                FOR (n:Service) ON (n.name)
            """,
            
            # Performance indexes for user management
            "user_id": """
                CREATE INDEX user_id IF NOT EXISTS
                FOR (u:User) ON (u.user_id)
            """,
            "role_name": """
                CREATE INDEX role_name IF NOT EXISTS
                FOR (r:Role) ON (r.name)
            """,
        }

        results = {}
        for name, query in indexes.items():
            try:
                await self.client.execute_write(query)
                logger.info(f"Created index: {name}")
                results[name] = True
            except Exception as e:
                logger.error(f"Failed to create index {name}: {e}")
                results[name] = False

        return results

    async def create_constraints(self) -> dict[str, bool]:
        """Create uniqueness constraints for data integrity.
        
        Returns:
            Dictionary mapping constraint name to creation success status
        """
        constraints = {
            # Uniqueness constraints
            "unique_audit_event_id": """
                CREATE CONSTRAINT unique_audit_event_id IF NOT EXISTS
                FOR (e:AuditEvent) REQUIRE e.event_id IS UNIQUE
            """,
            "unique_user_id": """
                CREATE CONSTRAINT unique_user_id IF NOT EXISTS
                FOR (u:User) REQUIRE u.user_id IS UNIQUE
            """,
            "unique_role_name": """
                CREATE CONSTRAINT unique_role_name IF NOT EXISTS
                FOR (r:Role) REQUIRE r.name IS UNIQUE
            """,
        }

        results = {}
        for name, query in constraints.items():
            try:
                await self.client.execute_write(query)
                logger.info(f"Created constraint: {name}")
                results[name] = True
            except Exception as e:
                logger.error(f"Failed to create constraint {name}: {e}")
                results[name] = False

        return results

    async def list_indexes(self) -> list[dict[str, str]]:
        """List all indexes in the database.
        
        Returns:
            List of index information dictionaries
        """
        query = "SHOW INDEXES"
        try:
            results = await self.client.execute_read(query)
            return results
        except Exception as e:
            logger.error(f"Failed to list indexes: {e}")
            return []

    async def drop_index(self, index_name: str) -> bool:
        """Drop a specific index.
        
        Args:
            index_name: Name of the index to drop
            
        Returns:
            True if successful, False otherwise
        """
        query = f"DROP INDEX {index_name} IF EXISTS"
        try:
            await self.client.execute_write(query)
            logger.info(f"Dropped index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop index {index_name}: {e}")
            return False


__all__ = ["IndexManager"]
