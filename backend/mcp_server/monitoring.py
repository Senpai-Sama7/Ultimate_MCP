"""Monitoring and health check components for Ultimate MCP."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List

import psutil

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System performance metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_count: int
    load_average: List[float] = field(default_factory=list)


@dataclass
class ApplicationMetrics:
    """Application-specific metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    active_connections: int = 0
    
    # Execution metrics
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_execution_time: float = 0.0
    
    # Language breakdown
    executions_by_language: Dict[str, int] = field(default_factory=dict)
    
    # User metrics
    unique_users: int = 0
    authenticated_requests: int = 0
    public_requests: int = 0


class MetricsCollector:
    """Collects and aggregates application metrics."""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.request_times = deque(maxlen=max_history)
        self.execution_times = deque(maxlen=max_history)
        self.request_counts = defaultdict(int)
        self.execution_counts = defaultdict(int)
        self.language_counts = defaultdict(int)
        self.user_sessions = set()
        self.start_time = time.time()
        
    async def record_request(
        self, 
        method: str, 
        path: str, 
        status_code: int, 
        duration: float,
        user_id: str | None = None,
        authenticated: bool = False,
    ) -> None:
        """Record HTTP request metrics."""
        self.request_times.append(duration)
        self.request_counts["total"] += 1
        
        if 200 <= status_code < 400:
            self.request_counts["successful"] += 1
        else:
            self.request_counts["failed"] += 1
            
        if user_id:
            self.user_sessions.add(user_id)
            
        if authenticated:
            self.request_counts["authenticated"] += 1
        else:
            self.request_counts["public"] += 1
    
    async def record_execution(
        self,
        language: str,
        duration: float,
        success: bool,
        user_id: str | None = None,
    ) -> None:
        """Record code execution metrics."""
        self.execution_times.append(duration)
        self.execution_counts["total"] += 1
        self.language_counts[language] += 1
        
        if success:
            self.execution_counts["successful"] += 1
        else:
            self.execution_counts["failed"] += 1
            
        if user_id:
            self.user_sessions.add(user_id)
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Disk usage (root partition)
            disk = psutil.disk_usage("/")
            
            # Network stats
            network = psutil.net_io_counters()
            
            # Process count
            process_count = len(psutil.pids())
            
            # Load average (Unix-like systems)
            try:
                load_avg = list(psutil.getloadavg())
            except AttributeError:
                load_avg = []
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                memory_available_mb=memory.available / (1024 * 1024),
                disk_usage_percent=disk.percent,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                process_count=process_count,
                load_average=load_avg,
            )
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                process_count=0,
            )
    
    def get_application_metrics(self) -> ApplicationMetrics:
        """Get current application metrics."""
        avg_response_time = (
            sum(self.request_times) / len(self.request_times)
            if self.request_times else 0.0
        )
        
        avg_execution_time = (
            sum(self.execution_times) / len(self.execution_times)
            if self.execution_times else 0.0
        )
        
        return ApplicationMetrics(
            total_requests=self.request_counts["total"],
            successful_requests=self.request_counts["successful"],
            failed_requests=self.request_counts["failed"],
            average_response_time=avg_response_time,
            
            total_executions=self.execution_counts["total"],
            successful_executions=self.execution_counts["successful"],
            failed_executions=self.execution_counts["failed"],
            average_execution_time=avg_execution_time,
            
            executions_by_language=dict(self.language_counts),
            unique_users=len(self.user_sessions),
            authenticated_requests=self.request_counts["authenticated"],
            public_requests=self.request_counts["public"],
        )
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics."""
        system_metrics = self.get_system_metrics()
        app_metrics = self.get_application_metrics()
        
        uptime = time.time() - self.start_time
        
        return {
            "timestamp": time.time(),
            "uptime_seconds": uptime,
            "system": {
                "cpu_percent": system_metrics.cpu_percent,
                "memory_percent": system_metrics.memory_percent,
                "memory_used_mb": system_metrics.memory_used_mb,
                "memory_available_mb": system_metrics.memory_available_mb,
                "disk_usage_percent": system_metrics.disk_usage_percent,
                "network_bytes_sent": system_metrics.network_bytes_sent,
                "network_bytes_recv": system_metrics.network_bytes_recv,
                "process_count": system_metrics.process_count,
                "load_average": system_metrics.load_average,
            },
            "application": {
                "requests": {
                    "total": app_metrics.total_requests,
                    "successful": app_metrics.successful_requests,
                    "failed": app_metrics.failed_requests,
                    "success_rate": (
                        app_metrics.successful_requests / app_metrics.total_requests
                        if app_metrics.total_requests > 0 else 0.0
                    ),
                    "average_response_time": app_metrics.average_response_time,
                    "requests_per_second": app_metrics.total_requests / uptime if uptime > 0 else 0.0,
                },
                "executions": {
                    "total": app_metrics.total_executions,
                    "successful": app_metrics.successful_executions,
                    "failed": app_metrics.failed_executions,
                    "success_rate": (
                        app_metrics.successful_executions / app_metrics.total_executions
                        if app_metrics.total_executions > 0 else 0.0
                    ),
                    "average_execution_time": app_metrics.average_execution_time,
                    "by_language": app_metrics.executions_by_language,
                },
                "users": {
                    "unique_users": app_metrics.unique_users,
                    "authenticated_requests": app_metrics.authenticated_requests,
                    "public_requests": app_metrics.public_requests,
                },
            },
        }


class HealthChecker:
    """Comprehensive health checking for all system components."""
    
    def __init__(self, neo4j_client):
        self.neo4j_client = neo4j_client
        self.monitoring_task = None
        self.health_history = deque(maxlen=100)
        self.is_monitoring = False
        
    async def check_database_health(self) -> Dict[str, Any]:
        """Check Neo4j database health."""
        try:
            start_time = time.time()
            is_healthy = await self.neo4j_client.health_check()
            response_time = time.time() - start_time
            
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "response_time": response_time,
                "error": None,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "response_time": None,
                "error": str(e),
            }
    
    async def check_system_health(self) -> Dict[str, Any]:
        """Check system resource health."""
        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_healthy = cpu_percent < 90.0
            
            # Check memory usage
            memory = psutil.virtual_memory()
            memory_healthy = memory.percent < 90.0
            
            # Check disk usage
            disk = psutil.disk_usage("/")
            disk_healthy = disk.percent < 90.0
            
            overall_healthy = cpu_healthy and memory_healthy and disk_healthy
            
            return {
                "status": "healthy" if overall_healthy else "degraded",
                "cpu": {
                    "percent": cpu_percent,
                    "healthy": cpu_healthy,
                },
                "memory": {
                    "percent": memory.percent,
                    "healthy": memory_healthy,
                },
                "disk": {
                    "percent": disk.percent,
                    "healthy": disk_healthy,
                },
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        
        # Check all components
        database_health = await self.check_database_health()
        system_health = await self.check_system_health()
        
        # Determine overall status
        components_healthy = (
            database_health["status"] == "healthy" and
            system_health["status"] in ["healthy", "degraded"]
        )
        
        overall_status = "healthy" if components_healthy else "unhealthy"
        
        health_data = {
            "status": overall_status,
            "timestamp": time.time(),
            "components": {
                "database": database_health,
                "system": system_health,
            },
        }
        
        # Store in history
        self.health_history.append(health_data)
        
        return health_data
    
    async def start_monitoring(self, interval: int = 30) -> None:
        """Start continuous health monitoring."""
        if self.is_monitoring:
            return
            
        self.is_monitoring = True
        
        async def monitor():
            while self.is_monitoring:
                try:
                    health_status = await self.get_health_status()
                    
                    if health_status["status"] != "healthy":
                        logger.warning(
                            "Health check failed",
                            status=health_status["status"],
                            components=health_status["components"],
                        )
                    
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
                    await asyncio.sleep(interval)
        
        self.monitoring_task = asyncio.create_task(monitor())
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitoring stopped")
    
    def get_health_history(self) -> List[Dict[str, Any]]:
        """Get recent health check history."""
        return list(self.health_history)


__all__ = [
    "MetricsCollector",
    "HealthChecker", 
    "SystemMetrics",
    "ApplicationMetrics"
]
