"""Enterprise audit logging for security and compliance."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of auditable events."""

    # Authentication events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    TOKEN_VALIDATION = "token_validation"

    # Authorization events
    AUTHZ_GRANTED = "authz_granted"
    AUTHZ_DENIED = "authz_denied"

    # Data access events
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"

    # Code execution events
    CODE_EXECUTION = "code_execution"
    CODE_LINT = "code_lint"
    CODE_TEST = "code_test"
    CODE_GENERATION = "code_generation"

    # Graph operations
    GRAPH_QUERY = "graph_query"
    GRAPH_UPSERT = "graph_upsert"

    # System events
    SYSTEM_ERROR = "system_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class AuditEvent:
    """Audit event data structure."""

    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    user_id: str | None
    ip_address: str | None
    user_agent: str | None
    resource: str
    action: str
    success: bool
    details: dict[str, Any]
    request_id: str | None = None
    session_id: str | None = None
    duration_ms: float | None = None
    error_message: str | None = None


class AuditLogger:
    """Enterprise audit logger for security and compliance tracking."""

    def __init__(self, neo4j_client: Any = None):
        """Initialize audit logger.

        Args:
            neo4j_client: Optional Neo4j client for persistence
        """
        self.neo4j_client = neo4j_client
        self.logger = logging.getLogger("ultimate_mcp.audit")

    async def log_event(self, event: AuditEvent) -> None:
        """Log an audit event.

        Args:
            event: Audit event to log
        """
        # Structured logging
        self.logger.info(
            "audit_event",
            extra={
                "audit_event_id": event.event_id,
                "event_type": event.event_type.value,
                "user_id": event.user_id,
                "resource": event.resource,
                "action": event.action,
                "success": event.success,
                "timestamp": event.timestamp.isoformat(),
            },
        )

        # Persist to Neo4j if available
        if self.neo4j_client:
            try:
                await self._persist_to_neo4j(event)
            except Exception as e:
                logger.error(f"Failed to persist audit event to Neo4j: {e}")

    async def _persist_to_neo4j(self, event: AuditEvent) -> None:
        """Persist audit event to Neo4j.

        Args:
            event: Audit event to persist
        """
        query = """
        CREATE (e:AuditEvent {
            event_id: $event_id,
            event_type: $event_type,
            timestamp: datetime($timestamp),
            user_id: $user_id,
            ip_address: $ip_address,
            user_agent: $user_agent,
            resource: $resource,
            action: $action,
            success: $success,
            details: $details,
            request_id: $request_id,
            session_id: $session_id,
            duration_ms: $duration_ms,
            error_message: $error_message
        })
        """
        parameters = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "user_id": event.user_id,
            "ip_address": event.ip_address,
            "user_agent": event.user_agent,
            "resource": event.resource,
            "action": event.action,
            "success": event.success,
            "details": event.details,
            "request_id": event.request_id,
            "session_id": event.session_id,
            "duration_ms": event.duration_ms,
            "error_message": event.error_message,
        }

        await self.neo4j_client.execute_write(query, parameters)

    async def log_authentication(
        self,
        success: bool,
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log authentication attempt.

        Args:
            success: Whether authentication succeeded
            user_id: User identifier (if available)
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request ID for correlation
            error_message: Error message if failed
        """
        import uuid

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.AUTH_SUCCESS if success else AuditEventType.AUTH_FAILURE,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource="auth",
            action="authenticate",
            success=success,
            details={"method": "bearer_token"},
            request_id=request_id,
            error_message=error_message,
        )
        await self.log_event(event)

    async def log_authorization(
        self,
        user_id: str,
        resource: str,
        action: str,
        granted: bool,
        ip_address: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log authorization decision.

        Args:
            user_id: User identifier
            resource: Resource being accessed
            action: Action being performed
            granted: Whether access was granted
            ip_address: Client IP address
            request_id: Request ID for correlation
            details: Additional context
        """
        import uuid

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.AUTHZ_GRANTED if granted else AuditEventType.AUTHZ_DENIED,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=None,
            resource=resource,
            action=action,
            success=granted,
            details=details or {},
            request_id=request_id,
        )
        await self.log_event(event)

    async def log_code_execution(
        self,
        user_id: str | None,
        code_hash: str,
        language: str,
        success: bool,
        duration_ms: float,
        ip_address: str | None = None,
        request_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log code execution event.

        Args:
            user_id: User identifier
            code_hash: Hash of executed code
            language: Programming language
            success: Whether execution succeeded
            duration_ms: Execution duration
            ip_address: Client IP address
            request_id: Request ID for correlation
            error_message: Error message if failed
        """
        import uuid

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.CODE_EXECUTION,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=None,
            resource="code_execution",
            action="execute",
            success=success,
            details={"code_hash": code_hash, "language": language},
            request_id=request_id,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        await self.log_event(event)

    async def log_security_violation(
        self,
        user_id: str | None,
        violation_type: str,
        details: dict[str, Any],
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log security violation.

        Args:
            user_id: User identifier
            violation_type: Type of violation
            details: Violation details
            ip_address: Client IP address
            request_id: Request ID for correlation
        """
        import uuid

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.SECURITY_VIOLATION,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=None,
            resource="security",
            action=violation_type,
            success=False,
            details=details,
            request_id=request_id,
        )
        await self.log_event(event)

    async def query_audit_log(
        self,
        event_type: AuditEventType | None = None,
        user_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit log.

        Args:
            event_type: Filter by event type
            user_id: Filter by user ID
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum results

        Returns:
            List of audit events
        """
        if not self.neo4j_client:
            return []

        conditions = []
        parameters: dict[str, Any] = {"limit": limit}

        if event_type:
            conditions.append("e.event_type = $event_type")
            parameters["event_type"] = event_type.value

        if user_id:
            conditions.append("e.user_id = $user_id")
            parameters["user_id"] = user_id

        if start_time:
            conditions.append("e.timestamp >= datetime($start_time)")
            parameters["start_time"] = start_time.isoformat()

        if end_time:
            conditions.append("e.timestamp <= datetime($end_time)")
            parameters["end_time"] = end_time.isoformat()

        where_clause = " AND ".join(conditions) if conditions else "true"
        query = f"""
        MATCH (e:AuditEvent)
        WHERE {where_clause}
        RETURN e
        ORDER BY e.timestamp DESC
        LIMIT $limit
        """

        results = await self.neo4j_client.execute_read(query, parameters)
        return results
