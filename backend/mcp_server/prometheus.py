"""Prometheus metrics export for observability."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .monitoring import MetricsCollector
    from .utils.cache import InMemoryCache
    from .utils.circuit_breaker import CircuitBreakerRegistry


class PrometheusExporter:
    """Export metrics in Prometheus format.
    
    Generates metrics in Prometheus text exposition format for scraping.
    """
    
    def __init__(
        self,
        metrics_collector: MetricsCollector | None = None,
        cache: InMemoryCache | None = None,
        circuit_breakers: CircuitBreakerRegistry | None = None,
    ):
        """Initialize Prometheus exporter.
        
        Args:
            metrics_collector: Application metrics collector
            cache: Cache instance for cache metrics
            circuit_breakers: Circuit breaker registry for resilience metrics
        """
        self.metrics_collector = metrics_collector
        self.cache = cache
        self.circuit_breakers = circuit_breakers
        self._app_start_time = time.time()
    
    async def generate_metrics(self) -> str:
        """Generate Prometheus metrics in text format.
        
        Returns:
            Metrics in Prometheus exposition format
        """
        lines = []
        
        # Process info
        lines.extend(self._generate_process_metrics())
        
        # Application metrics
        if self.metrics_collector:
            lines.extend(await self._generate_application_metrics())
        
        # Cache metrics
        if self.cache:
            lines.extend(self._generate_cache_metrics())
        
        # Circuit breaker metrics
        if self.circuit_breakers:
            lines.extend(await self._generate_circuit_breaker_metrics())
        
        return "\n".join(lines) + "\n"
    
    def _generate_process_metrics(self) -> list[str]:
        """Generate process-level metrics."""
        uptime = time.time() - self._app_start_time
        
        return [
            "# HELP ultimate_mcp_process_uptime_seconds Process uptime in seconds",
            "# TYPE ultimate_mcp_process_uptime_seconds gauge",
            f"ultimate_mcp_process_uptime_seconds {uptime:.2f}",
            "",
            "# HELP ultimate_mcp_process_start_time_seconds Process start time in unix epoch",
            "# TYPE ultimate_mcp_process_start_time_seconds gauge",
            f"ultimate_mcp_process_start_time_seconds {self._app_start_time:.2f}",
            "",
        ]
    
    async def _generate_application_metrics(self) -> list[str]:
        """Generate application metrics."""
        if not self.metrics_collector:
            return []
        
        metrics = await self.metrics_collector.get_metrics()
        app_metrics = metrics.get("application", {})
        system_metrics = metrics.get("system", {})
        
        lines = []
        
        # HTTP requests
        req_metrics = app_metrics.get("requests", {})
        lines.extend([
            "# HELP ultimate_mcp_http_requests_total Total HTTP requests",
            "# TYPE ultimate_mcp_http_requests_total counter",
            f"ultimate_mcp_http_requests_total{{status=\"total\"}} {req_metrics.get('total', 0)}",
            f"ultimate_mcp_http_requests_total{{status=\"successful\"}} {req_metrics.get('successful', 0)}",
            f"ultimate_mcp_http_requests_total{{status=\"failed\"}} {req_metrics.get('failed', 0)}",
            "",
            "# HELP ultimate_mcp_http_request_duration_seconds Average HTTP request duration",
            "# TYPE ultimate_mcp_http_request_duration_seconds gauge",
            f"ultimate_mcp_http_request_duration_seconds {req_metrics.get('average_response_time', 0):.6f}",
            "",
            "# HELP ultimate_mcp_http_requests_rate Requests per second",
            "# TYPE ultimate_mcp_http_requests_rate gauge",
            f"ultimate_mcp_http_requests_rate {req_metrics.get('requests_per_second', 0):.2f}",
            "",
        ])
        
        # Code executions
        exec_metrics = app_metrics.get("executions", {})
        lines.extend([
            "# HELP ultimate_mcp_code_executions_total Total code executions",
            "# TYPE ultimate_mcp_code_executions_total counter",
            f"ultimate_mcp_code_executions_total{{status=\"total\"}} {exec_metrics.get('total', 0)}",
            f"ultimate_mcp_code_executions_total{{status=\"successful\"}} {exec_metrics.get('successful', 0)}",
            f"ultimate_mcp_code_executions_total{{status=\"failed\"}} {exec_metrics.get('failed', 0)}",
            "",
            "# HELP ultimate_mcp_code_execution_duration_seconds Average code execution duration",
            "# TYPE ultimate_mcp_code_execution_duration_seconds gauge",
            f"ultimate_mcp_code_execution_duration_seconds {exec_metrics.get('average_execution_time', 0):.6f}",
            "",
        ])
        
        # Executions by language
        by_lang = exec_metrics.get("by_language", {})
        if by_lang:
            lines.append("# HELP ultimate_mcp_executions_by_language Executions by programming language")
            lines.append("# TYPE ultimate_mcp_executions_by_language counter")
            for language, count in by_lang.items():
                lines.append(f'ultimate_mcp_executions_by_language{{language="{language}"}} {count}')
            lines.append("")
        
        # User metrics
        user_metrics = app_metrics.get("users", {})
        lines.extend([
            "# HELP ultimate_mcp_unique_users Number of unique users",
            "# TYPE ultimate_mcp_unique_users gauge",
            f"ultimate_mcp_unique_users {user_metrics.get('unique_users', 0)}",
            "",
            "# HELP ultimate_mcp_requests_by_auth Requests by authentication status",
            "# TYPE ultimate_mcp_requests_by_auth counter",
            f"ultimate_mcp_requests_by_auth{{authenticated=\"true\"}} {user_metrics.get('authenticated_requests', 0)}",
            f"ultimate_mcp_requests_by_auth{{authenticated=\"false\"}} {user_metrics.get('public_requests', 0)}",
            "",
        ])
        
        # System metrics
        lines.extend([
            "# HELP ultimate_mcp_cpu_usage_percent CPU usage percentage",
            "# TYPE ultimate_mcp_cpu_usage_percent gauge",
            f"ultimate_mcp_cpu_usage_percent {system_metrics.get('cpu_percent', 0):.2f}",
            "",
            "# HELP ultimate_mcp_memory_usage_percent Memory usage percentage",
            "# TYPE ultimate_mcp_memory_usage_percent gauge",
            f"ultimate_mcp_memory_usage_percent {system_metrics.get('memory_percent', 0):.2f}",
            "",
            "# HELP ultimate_mcp_memory_used_bytes Memory used in bytes",
            "# TYPE ultimate_mcp_memory_used_bytes gauge",
            f"ultimate_mcp_memory_used_bytes {system_metrics.get('memory_used_mb', 0) * 1024 * 1024:.0f}",
            "",
            "# HELP ultimate_mcp_disk_usage_percent Disk usage percentage",
            "# TYPE ultimate_mcp_disk_usage_percent gauge",
            f"ultimate_mcp_disk_usage_percent {system_metrics.get('disk_usage_percent', 0):.2f}",
            "",
        ])
        
        # Load average (if available)
        load_avg = system_metrics.get("load_average", [])
        if load_avg and len(load_avg) >= 3:
            lines.extend([
                "# HELP ultimate_mcp_load_average System load average",
                "# TYPE ultimate_mcp_load_average gauge",
                f"ultimate_mcp_load_average{{period=\"1m\"}} {load_avg[0]:.2f}",
                f"ultimate_mcp_load_average{{period=\"5m\"}} {load_avg[1]:.2f}",
                f"ultimate_mcp_load_average{{period=\"15m\"}} {load_avg[2]:.2f}",
                "",
            ])
        
        return lines
    
    def _generate_cache_metrics(self) -> list[str]:
        """Generate cache metrics."""
        if not self.cache:
            return []
        
        stats = self.cache.get_stats()
        metrics_data = stats.get("metrics", {})
        
        return [
            "# HELP ultimate_mcp_cache_size Current cache size",
            "# TYPE ultimate_mcp_cache_size gauge",
            f"ultimate_mcp_cache_size {stats.get('size', 0)}",
            "",
            "# HELP ultimate_mcp_cache_utilization Cache utilization (0-1)",
            "# TYPE ultimate_mcp_cache_utilization gauge",
            f"ultimate_mcp_cache_utilization {stats.get('utilization', 0):.4f}",
            "",
            "# HELP ultimate_mcp_cache_operations_total Total cache operations",
            "# TYPE ultimate_mcp_cache_operations_total counter",
            f"ultimate_mcp_cache_operations_total{{operation=\"hit\"}} {metrics_data.get('hits', 0)}",
            f"ultimate_mcp_cache_operations_total{{operation=\"miss\"}} {metrics_data.get('misses', 0)}",
            f"ultimate_mcp_cache_operations_total{{operation=\"eviction\"}} {metrics_data.get('evictions', 0)}",
            "",
            "# HELP ultimate_mcp_cache_hit_rate Cache hit rate (0-1)",
            "# TYPE ultimate_mcp_cache_hit_rate gauge",
            f"ultimate_mcp_cache_hit_rate {metrics_data.get('hit_rate', 0):.4f}",
            "",
        ]
    
    async def _generate_circuit_breaker_metrics(self) -> list[str]:
        """Generate circuit breaker metrics."""
        if not self.circuit_breakers:
            return []
        
        all_metrics = await self.circuit_breakers.get_all_metrics()
        
        lines = []
        
        for name, metrics in all_metrics.items():
            state = metrics.get("state", "unknown")
            lines.extend([
                f"# HELP ultimate_mcp_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half_open)",
                f"# TYPE ultimate_mcp_circuit_breaker_state gauge",
                f'ultimate_mcp_circuit_breaker_state{{breaker="{name}"}} {self._state_to_value(state)}',
                "",
                f"# HELP ultimate_mcp_circuit_breaker_calls_total Total calls through circuit breaker",
                f"# TYPE ultimate_mcp_circuit_breaker_calls_total counter",
                f'ultimate_mcp_circuit_breaker_calls_total{{breaker="{name}",status="total"}} {metrics.get("total_calls", 0)}',
                f'ultimate_mcp_circuit_breaker_calls_total{{breaker="{name}",status="success"}} {metrics.get("successful_calls", 0)}',
                f'ultimate_mcp_circuit_breaker_calls_total{{breaker="{name}",status="failed"}} {metrics.get("failed_calls", 0)}',
                f'ultimate_mcp_circuit_breaker_calls_total{{breaker="{name}",status="rejected"}} {metrics.get("rejected_calls", 0)}',
                "",
            ])
        
        return lines
    
    def _state_to_value(self, state: str) -> int:
        """Convert circuit breaker state to numeric value."""
        return {"closed": 0, "open": 1, "half_open": 2}.get(state, -1)


def format_metric_line(
    metric_name: str,
    value: Any,
    labels: dict[str, str] | None = None,
) -> str:
    """Format a single metric line in Prometheus format.
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        labels: Optional labels dictionary
        
    Returns:
        Formatted metric line
    """
    if labels:
        label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
        return f"{metric_name}{{{label_str}}} {value}"
    return f"{metric_name} {value}"


__all__ = [
    "PrometheusExporter",
    "format_metric_line",
]
