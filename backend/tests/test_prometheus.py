"""Tests for Prometheus metrics export."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp_server.prometheus import PrometheusExporter, format_metric_line


@pytest.fixture
def mock_metrics_collector():
    """Create mock metrics collector."""
    collector = MagicMock()
    collector.get_metrics = AsyncMock(return_value={
        "timestamp": 1234567890.0,
        "uptime_seconds": 3600.0,
        "system": {
            "cpu_percent": 45.2,
            "memory_percent": 62.5,
            "memory_used_mb": 1024.0,
            "memory_available_mb": 512.0,
            "disk_usage_percent": 75.0,
            "load_average": [1.5, 1.2, 1.0],
        },
        "application": {
            "requests": {
                "total": 1000,
                "successful": 950,
                "failed": 50,
                "success_rate": 0.95,
                "average_response_time": 0.125,
                "requests_per_second": 2.5,
            },
            "executions": {
                "total": 500,
                "successful": 475,
                "failed": 25,
                "success_rate": 0.95,
                "average_execution_time": 1.5,
                "by_language": {
                    "python": 300,
                    "javascript": 200,
                },
            },
            "users": {
                "unique_users": 25,
                "authenticated_requests": 800,
                "public_requests": 200,
            },
        },
    })
    return collector


@pytest.fixture
def mock_cache():
    """Create mock cache."""
    cache = MagicMock()
    cache.get_stats = MagicMock(return_value={
        "size": 150,
        "max_size": 1000,
        "utilization": 0.15,
        "metrics": {
            "hits": 500,
            "misses": 100,
            "evictions": 25,
            "hit_rate": 0.8333,
        },
    })
    return cache


@pytest.fixture
def mock_circuit_breakers():
    """Create mock circuit breaker registry."""
    registry = MagicMock()
    registry.get_all_metrics = AsyncMock(return_value={
        "neo4j_client": {
            "state": "closed",
            "total_calls": 1000,
            "successful_calls": 990,
            "failed_calls": 10,
            "rejected_calls": 0,
        },
        "external_api": {
            "state": "open",
            "total_calls": 500,
            "successful_calls": 400,
            "failed_calls": 100,
            "rejected_calls": 50,
        },
    })
    return registry


@pytest.mark.asyncio
async def test_prometheus_exporter_basic(mock_metrics_collector):
    """Test basic Prometheus metrics generation."""
    exporter = PrometheusExporter(metrics_collector=mock_metrics_collector)
    
    metrics = await exporter.generate_metrics()
    
    assert isinstance(metrics, str)
    assert len(metrics) > 0
    # Check for Prometheus format headers
    assert "# HELP" in metrics
    assert "# TYPE" in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_process_metrics():
    """Test process-level metrics generation."""
    exporter = PrometheusExporter()
    
    metrics = await exporter.generate_metrics()
    
    # Check for uptime metric
    assert "ultimate_mcp_process_uptime_seconds" in metrics
    assert "ultimate_mcp_process_start_time_seconds" in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_http_metrics(mock_metrics_collector):
    """Test HTTP request metrics."""
    exporter = PrometheusExporter(metrics_collector=mock_metrics_collector)
    
    metrics = await exporter.generate_metrics()
    
    # Check for HTTP metrics
    assert "ultimate_mcp_http_requests_total" in metrics
    assert 'status="total"' in metrics
    assert 'status="successful"' in metrics
    assert 'status="failed"' in metrics
    assert "ultimate_mcp_http_request_duration_seconds" in metrics
    assert "ultimate_mcp_http_requests_rate" in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_execution_metrics(mock_metrics_collector):
    """Test code execution metrics."""
    exporter = PrometheusExporter(metrics_collector=mock_metrics_collector)
    
    metrics = await exporter.generate_metrics()
    
    # Check for execution metrics
    assert "ultimate_mcp_code_executions_total" in metrics
    assert "ultimate_mcp_code_execution_duration_seconds" in metrics
    assert "ultimate_mcp_executions_by_language" in metrics
    assert 'language="python"' in metrics
    assert 'language="javascript"' in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_system_metrics(mock_metrics_collector):
    """Test system resource metrics."""
    exporter = PrometheusExporter(metrics_collector=mock_metrics_collector)
    
    metrics = await exporter.generate_metrics()
    
    # Check for system metrics
    assert "ultimate_mcp_cpu_usage_percent" in metrics
    assert "ultimate_mcp_memory_usage_percent" in metrics
    assert "ultimate_mcp_memory_used_bytes" in metrics
    assert "ultimate_mcp_disk_usage_percent" in metrics
    assert "ultimate_mcp_load_average" in metrics
    assert 'period="1m"' in metrics
    assert 'period="5m"' in metrics
    assert 'period="15m"' in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_user_metrics(mock_metrics_collector):
    """Test user-related metrics."""
    exporter = PrometheusExporter(metrics_collector=mock_metrics_collector)
    
    metrics = await exporter.generate_metrics()
    
    # Check for user metrics
    assert "ultimate_mcp_unique_users" in metrics
    assert "ultimate_mcp_requests_by_auth" in metrics
    assert 'authenticated="true"' in metrics
    assert 'authenticated="false"' in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_cache_metrics(mock_cache):
    """Test cache metrics."""
    exporter = PrometheusExporter(cache=mock_cache)
    
    metrics = await exporter.generate_metrics()
    
    # Check for cache metrics
    assert "ultimate_mcp_cache_size" in metrics
    assert "ultimate_mcp_cache_utilization" in metrics
    assert "ultimate_mcp_cache_operations_total" in metrics
    assert 'operation="hit"' in metrics
    assert 'operation="miss"' in metrics
    assert 'operation="eviction"' in metrics
    assert "ultimate_mcp_cache_hit_rate" in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_circuit_breaker_metrics(mock_circuit_breakers):
    """Test circuit breaker metrics."""
    exporter = PrometheusExporter(circuit_breakers=mock_circuit_breakers)
    
    metrics = await exporter.generate_metrics()
    
    # Check for circuit breaker metrics
    assert "ultimate_mcp_circuit_breaker_state" in metrics
    assert "ultimate_mcp_circuit_breaker_calls_total" in metrics
    assert 'breaker="neo4j_client"' in metrics
    assert 'breaker="external_api"' in metrics
    assert 'status="success"' in metrics
    assert 'status="failed"' in metrics
    assert 'status="rejected"' in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_combined_metrics(
    mock_metrics_collector,
    mock_cache,
    mock_circuit_breakers,
):
    """Test generation of all metrics combined."""
    exporter = PrometheusExporter(
        metrics_collector=mock_metrics_collector,
        cache=mock_cache,
        circuit_breakers=mock_circuit_breakers,
    )
    
    metrics = await exporter.generate_metrics()
    
    # Should include all types of metrics
    assert "ultimate_mcp_process_uptime_seconds" in metrics
    assert "ultimate_mcp_http_requests_total" in metrics
    assert "ultimate_mcp_cache_size" in metrics
    assert "ultimate_mcp_circuit_breaker_state" in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_state_conversion():
    """Test circuit breaker state to value conversion."""
    exporter = PrometheusExporter()
    
    assert exporter._state_to_value("closed") == 0
    assert exporter._state_to_value("open") == 1
    assert exporter._state_to_value("half_open") == 2
    assert exporter._state_to_value("unknown") == -1


def test_format_metric_line_no_labels():
    """Test formatting metric line without labels."""
    line = format_metric_line("my_metric", 42.5)
    assert line == "my_metric 42.5"


def test_format_metric_line_with_labels():
    """Test formatting metric line with labels."""
    line = format_metric_line(
        "my_metric",
        100,
        labels={"method": "GET", "status": "200"},
    )
    assert "my_metric{" in line
    assert 'method="GET"' in line
    assert 'status="200"' in line
    assert "} 100" in line


def test_format_metric_line_string_value():
    """Test formatting metric line with string value."""
    line = format_metric_line("my_metric", "value")
    assert line == "my_metric value"


def test_format_metric_line_empty_labels():
    """Test formatting metric line with empty labels dict."""
    line = format_metric_line("my_metric", 123, labels={})
    assert line == "my_metric 123"


@pytest.mark.asyncio
async def test_prometheus_exporter_no_components():
    """Test exporter with no components configured."""
    exporter = PrometheusExporter()
    
    metrics = await exporter.generate_metrics()
    
    # Should still generate process metrics
    assert "ultimate_mcp_process_uptime_seconds" in metrics
    # Should not have application/cache/breaker metrics
    assert "ultimate_mcp_http_requests_total" not in metrics
    assert "ultimate_mcp_cache_size" not in metrics
    assert "ultimate_mcp_circuit_breaker_state" not in metrics


@pytest.mark.asyncio
async def test_prometheus_exporter_valid_format(mock_metrics_collector):
    """Test that generated metrics are in valid Prometheus format."""
    exporter = PrometheusExporter(metrics_collector=mock_metrics_collector)
    
    metrics = await exporter.generate_metrics()
    
    lines = metrics.split("\n")
    
    # Check format of each line
    for line in lines:
        if line.startswith("#"):
            # Comment line
            assert "# HELP" in line or "# TYPE" in line
        elif line.strip():
            # Metric line
            assert " " in line  # Should have space between name and value
