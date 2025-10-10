"""Enhanced FastAPI application with comprehensive monitoring and error handling."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Callable

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastmcp import FastMCP
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from .audit import AuditLogger
from .auth import JWTHandler, RBACManager, Role, require_permission
from .config import config
from .database.neo4j_client import Neo4jClient
from .monitoring import HealthChecker, MetricsCollector
from .tools import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionTool,
)
from .utils.enhanced_security import (
    EnhancedSecurityManager,
    RateLimitConfig,
    SecurityContext,
    SecurityLevel,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if config.monitoring.log_format == "console" 
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, config.monitoring.log_level.upper())
    ),
    logger_factory=structlog.WriteLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request logging and monitoring."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging and metrics."""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Add request context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=get_remote_address(request),
            user_agent=request.headers.get("user-agent", ""),
        )
        
        logger.info("Request started")
        
        try:
            response = await call_next(request)
            
            # Log successful request
            duration = time.time() - start_time
            logger.info(
                "Request completed",
                status_code=response.status_code,
                duration=duration,
            )
            
            # Add response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                error=str(e),
                error_type=type(e).__name__,
                duration=duration,
            )
            
            # Return structured error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                headers={"X-Request-ID": request_id},
            )


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enhanced security middleware."""
    
    def __init__(self, app, security_manager: EnhancedSecurityManager):
        super().__init__(app)
        self.security_manager = security_manager
        self.rate_limit_config = RateLimitConfig(
            requests_per_minute=config.security.rate_limit_requests_per_minute,
            requests_per_hour=config.security.rate_limit_requests_per_hour,
            requests_per_day=config.security.rate_limit_requests_per_day,
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply security policies."""
        
        # Rate limiting
        client_ip = get_remote_address(request)
        if client_ip is None:
            client_ip = "unknown"

        if not self.security_manager.check_rate_limit(client_ip, self.rate_limit_config):
            logger.warning(
                "Rate limit exceeded",
                client_ip=client_ip,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
            )
        
        # Security headers
        response = await call_next(request)
        
        # Add security headers
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        })
        
        return response


# Global components
neo4j_client: Neo4jClient | None = None
security_manager: EnhancedSecurityManager | None = None
metrics_collector: MetricsCollector | None = None
health_checker: HealthChecker | None = None
audit_logger: AuditLogger | None = None
rbac_manager: RBACManager | None = None
jwt_handler: JWTHandler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Enhanced application lifespan with proper resource management."""
    global neo4j_client, security_manager, metrics_collector, health_checker
    global audit_logger, rbac_manager, jwt_handler
    
    logger.info("Starting Ultimate MCP server", version="2.0.0")
    
    try:
        # Initialize components
        neo4j_client = Neo4jClient(
            uri=config.database.uri,
            user=config.database.user,
            password=config.database.password,
            database=config.database.database,
        )
        
        security_manager = EnhancedSecurityManager(
            secret_key=config.security.secret_key,
            encryption_key=config.security.encryption_key,
        )
        
        metrics_collector = MetricsCollector()
        health_checker = HealthChecker(neo4j_client)
        
        # Connect to database
        await neo4j_client.connect()
        logger.info("Database connection established")
        
        # Initialize Phase 1 components
        audit_logger = AuditLogger(neo4j_client=neo4j_client)
        rbac_manager = RBACManager(neo4j_client=neo4j_client)
        jwt_handler = JWTHandler(secret_key=config.security.secret_key)
        
        # Store in app state for access in endpoints
        app.state.audit_logger = audit_logger
        app.state.rbac_manager = rbac_manager
        app.state.jwt_handler = jwt_handler
        
        logger.info("Audit logging, RBAC, and JWT authentication initialized")
        
        # Start health monitoring
        asyncio.create_task(health_checker.start_monitoring())
        
        logger.info("Server startup completed successfully")
        
        yield
        
    except Exception as e:
        logger.error("Failed to start server", error=str(e))
        raise
    finally:
        # Cleanup resources
        if neo4j_client:
            await neo4j_client.close()
        
        if health_checker:
            await health_checker.stop_monitoring()
        
        logger.info("Server shutdown completed")


# Create FastAPI application
app = FastAPI(
    title="Ultimate MCP Platform",
    description="Enhanced Model Context Protocol platform with comprehensive monitoring",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production else None,
    redoc_url="/redoc" if not config.is_production else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.allowed_origins,
    allow_credentials=True,
    allow_methods=config.server.allowed_methods,
    allow_headers=config.server.allowed_headers,
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda r, e: JSONResponse(
    status_code=429,
    content={"error": "Rate limit exceeded", "detail": str(e)}
))
app.add_middleware(SlowAPIMiddleware)

# Custom middleware
app.add_middleware(RequestLoggingMiddleware)

# Security setup
security = HTTPBearer(auto_error=False)


async def get_security_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> SecurityContext:
    """Get security context for request with JWT role extraction."""
    token = credentials.credentials if credentials else None
    
    # Create base security context
    context = security_manager.create_security_context(
        token=token,
        ip_address=get_remote_address(request),
        user_agent=request.headers.get("user-agent"),
    )
    
    # Extract roles from JWT if token provided and JWT handler available
    if token and jwt_handler:
        try:
            roles = jwt_handler.extract_roles(token)
            # Add roles to context (store as attribute)
            context.roles = roles
            
            # Log successful authentication
            if audit_logger:
                await audit_logger.log_authentication(
                    success=True,
                    user_id=context.user_id,
                    ip_address=get_remote_address(request),
                    user_agent=request.headers.get("user-agent"),
                    request_id=str(uuid.uuid4()),
                )
        except Exception as e:
            # Log failed authentication
            if audit_logger:
                await audit_logger.log_authentication(
                    success=False,
                    ip_address=get_remote_address(request),
                    user_agent=request.headers.get("user-agent"),
                    request_id=str(uuid.uuid4()),
                    error_message=str(e),
                )
            # Set viewer role as default on error
            context.roles = [Role.VIEWER]
    else:
        # No token, default to viewer
        context.roles = [Role.VIEWER]
    
    # Store context in request state for permission decorators
    request.state.security_context = context
    
    return context


async def require_authentication(
    security_context: SecurityContext = Depends(get_security_context),
) -> SecurityContext:
    """Require authenticated user."""
    if security_context.security_level == SecurityLevel.PUBLIC:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return security_context


# Health and monitoring endpoints
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Comprehensive health check endpoint."""
    if not health_checker:
        return {"status": "unhealthy", "error": "Health checker not initialized"}
    
    return await health_checker.get_health_status()


@app.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """Get application metrics."""
    if not metrics_collector:
        return {"error": "Metrics collector not initialized"}
    
    return await metrics_collector.get_metrics()


@app.get("/status")
async def get_status() -> dict[str, Any]:
    """Get detailed system status."""
    return {
        "service": "Ultimate MCP Platform",
        "version": "2.0.0",
        "environment": config.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0,
        "database": await neo4j_client.health_check() if neo4j_client else False,
        "security": {
            "rate_limiting": True,
            "authentication": True,
            "encryption": config.security.encryption_key is not None,
            "rbac": rbac_manager is not None,
            "audit_logging": audit_logger is not None,
        },
    }


# Role management endpoints
@app.post("/api/v1/users/{user_id}/roles")
@require_permission("system", "admin")
async def assign_user_role(
    user_id: str,
    role: str,
    request: Request,
    security_context: SecurityContext = Depends(get_security_context),
) -> dict[str, Any]:
    """Assign role to user (admin only)."""
    if not rbac_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RBAC manager not initialized",
        )
    
    try:
        # Validate role
        role_enum = Role(role)
        
        # Assign role
        await rbac_manager.assign_role(user_id, role_enum)
        
        # Log authorization grant
        if audit_logger:
            await audit_logger.log_authorization(
                user_id=security_context.user_id,
                resource="roles",
                action="assign",
                granted=True,
                ip_address=get_remote_address(request),
                request_id=str(uuid.uuid4()),
                details={"target_user": user_id, "role": role},
            )
        
        return {
            "success": True,
            "user_id": user_id,
            "role": role,
            "message": f"Role {role} assigned to user {user_id}",
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {role}. Must be one of: viewer, developer, admin",
        )


@app.get("/api/v1/users/{user_id}/roles")
@require_permission("system", "admin")
async def get_user_roles(
    user_id: str,
    request: Request,
    security_context: SecurityContext = Depends(get_security_context),
) -> dict[str, Any]:
    """Get user roles (admin only)."""
    if not rbac_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RBAC manager not initialized",
        )
    
    roles = await rbac_manager.get_user_roles(user_id)
    
    return {
        "user_id": user_id,
        "roles": [role.value for role in roles],
    }


@app.get("/api/v1/audit")
@require_permission("system", "admin")
async def query_audit_log(
    request: Request,
    event_type: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
    security_context: SecurityContext = Depends(get_security_context),
) -> dict[str, Any]:
    """Query audit log (admin only)."""
    if not audit_logger:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audit logger not initialized",
        )
    
    from .audit import AuditEventType
    
    # Parse event type if provided
    event_type_enum = None
    if event_type:
        try:
            event_type_enum = AuditEventType(event_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event type: {event_type}",
            )
    
    # Query audit log
    events = await audit_logger.query_audit_log(
        event_type=event_type_enum,
        user_id=user_id,
        limit=limit,
    )
    
    return {
        "total": len(events),
        "limit": limit,
        "filters": {
            "event_type": event_type,
            "user_id": user_id,
        },
        "events": events,
    }


# Enhanced tool endpoints with security
@app.post("/api/v1/execute", response_model=ExecutionResponse)
@limiter.limit("10/minute")
@require_permission("tools", "execute")
async def execute_code(
    request: Request,
    execution_request: ExecutionRequest,
    security_context: SecurityContext = Depends(get_security_context),
) -> ExecutionResponse:
    """Execute code with enhanced security and monitoring."""
    
    start_time = time.time()
    code_hash = hashlib.sha256(execution_request.code.encode()).hexdigest()
    
    # Check permissions for code execution
    if (security_context.security_level == SecurityLevel.PUBLIC and 
        len(execution_request.code) > 1000):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public users limited to 1000 characters of code",
        )
    
    tool = ExecutionTool(neo4j_client)
    
    try:
        result = await tool.run(execution_request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log successful execution
        if audit_logger:
            await audit_logger.log_code_execution(
                user_id=security_context.user_id,
                code_hash=code_hash,
                language=execution_request.language,
                success=result.return_code == 0,
                duration_ms=duration_ms,
                ip_address=get_remote_address(request),
                request_id=str(uuid.uuid4()),
            )
        
        # Record metrics
        if metrics_collector:
            await metrics_collector.record_execution(
                language=execution_request.language,
                duration=result.duration_seconds,
                success=result.return_code == 0,
                user_id=security_context.user_id,
            )
        
        return result
        
    except Exception as e:
        # Log failed execution
        duration_ms = (time.time() - start_time) * 1000
        
        if audit_logger:
            await audit_logger.log_code_execution(
                user_id=security_context.user_id,
                code_hash=code_hash,
                language=execution_request.language,
                success=False,
                duration_ms=duration_ms,
                ip_address=get_remote_address(request),
                request_id=str(uuid.uuid4()),
                error_message=str(e),
            )
        
        logger.error("Code execution failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}",
        )


# MCP integration with enhanced security
mcp = FastMCP("Ultimate MCP Enhanced")

@mcp.tool()
async def enhanced_execute(
    code: str,
    language: str = "python",
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """Enhanced MCP execute tool with security."""
    
    # Create execution request
    request = ExecutionRequest(
        code=code,
        language=language,
        timeout_seconds=timeout_seconds,
    )
    
    # Execute with public security context
    tool = ExecutionTool(neo4j_client)
    result = await tool.run(request)
    
    return {
        "id": result.id,
        "return_code": result.return_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_seconds": result.duration_seconds,
    }


# Mount MCP server
app.mount("/mcp", mcp.create_app())


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Enhanced HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """General exception handler with logging."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
        },
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Record startup time."""
    app.state.start_time = time.time()
    logger.info("Enhanced Ultimate MCP server started successfully")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "enhanced_server:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.reload,
        log_level=config.monitoring.log_level.lower(),
    )
