"""Enhanced FastAPI application with comprehensive monitoring and error handling."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime
from typing import Any, Awaitable, Callable

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastmcp import Context as MCPContext
from fastmcp import FastMCP
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from .config import config
from .database.neo4j_client import Neo4jClient
from .monitoring import MetricsCollector, HealthChecker
from .tools import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionTool,
    GenerationRequest,
    GenerationResponse,
    GenerationTool,
    GraphQueryResponse,
    GraphTool,
    GraphUpsertResponse,
    LintRequest,
    LintResponse,
    LintTool,
    TestRequest,
    TestResponse,
    TestTool,
)
from .utils.enhanced_security import EnhancedSecurityManager, SecurityContext, SecurityLevel

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
                    "timestamp": datetime.utcnow().isoformat(),
                },
                headers={"X-Request-ID": request_id},
            )


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enhanced security middleware."""
    
    def __init__(self, app, security_manager: EnhancedSecurityManager):
        super().__init__(app)
        self.security_manager = security_manager
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply security policies."""
        
        # Rate limiting
        client_ip = get_remote_address(request)
        if not self.security_manager.check_rate_limit(
            client_ip, 
            config.security.rate_limit_requests_per_minute
        ):
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Enhanced application lifespan with proper resource management."""
    global neo4j_client, security_manager, metrics_collector, health_checker
    
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
    """Get security context for request."""
    token = credentials.credentials if credentials else None
    
    return security_manager.create_security_context(
        token=token,
        ip_address=get_remote_address(request),
        user_agent=request.headers.get("user-agent"),
    )


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
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0,
        "database": await neo4j_client.health_check() if neo4j_client else False,
        "security": {
            "rate_limiting": True,
            "authentication": True,
            "encryption": config.security.encryption_key is not None,
        },
    }


# Enhanced tool endpoints with security
@app.post("/api/v1/execute", response_model=ExecutionResponse)
@limiter.limit("10/minute")
async def execute_code(
    request: Request,
    execution_request: ExecutionRequest,
    security_context: SecurityContext = Depends(get_security_context),
) -> ExecutionResponse:
    """Execute code with enhanced security and monitoring."""
    
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
            "timestamp": datetime.utcnow().isoformat(),
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
            "timestamp": datetime.utcnow().isoformat(),
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
