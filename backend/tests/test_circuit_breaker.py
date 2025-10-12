"""Tests for circuit breaker implementation."""

from __future__ import annotations

import asyncio

import pytest
from mcp_server.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
)


@pytest.fixture
def circuit_breaker():
    """Create circuit breaker with test configuration."""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=1.0,
        half_open_max_calls=2,
    )
    return CircuitBreaker("test", config)


@pytest.mark.asyncio
async def test_circuit_breaker_closed_state(circuit_breaker):
    """Test circuit breaker in CLOSED state."""
    assert circuit_breaker.state == CircuitState.CLOSED
    assert circuit_breaker.is_closed
    assert not circuit_breaker.is_open
    assert not circuit_breaker.is_half_open


@pytest.mark.asyncio
async def test_successful_call(circuit_breaker):
    """Test successful call through circuit breaker."""
    async def success_func():
        return "success"

    result = await circuit_breaker.call(success_func)
    assert result == "success"
    assert circuit_breaker.metrics.successful_calls == 1
    assert circuit_breaker.metrics.failed_calls == 0
    assert circuit_breaker.is_closed


@pytest.mark.asyncio
async def test_failed_call(circuit_breaker):
    """Test failed call through circuit breaker."""
    async def failing_func():
        raise ValueError("test error")

    with pytest.raises(ValueError, match="test error"):
        await circuit_breaker.call(failing_func)
    
    assert circuit_breaker.metrics.failed_calls == 1
    assert circuit_breaker.is_closed  # Still closed, under threshold


@pytest.mark.asyncio
async def test_circuit_opens_on_failures(circuit_breaker):
    """Test circuit opens after failure threshold."""
    async def failing_func():
        raise ValueError("test error")

    # Trigger failures up to threshold
    for _ in range(circuit_breaker.config.failure_threshold):
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

    # Circuit should now be open
    assert circuit_breaker.is_open
    assert circuit_breaker.metrics.failed_calls == 3


@pytest.mark.asyncio
async def test_circuit_rejects_when_open(circuit_breaker):
    """Test circuit rejects calls when open."""
    async def failing_func():
        raise ValueError("test error")

    # Open the circuit
    for _ in range(circuit_breaker.config.failure_threshold):
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

    assert circuit_breaker.is_open

    # Try to make a call - should be rejected
    async def any_func():
        return "should not execute"

    with pytest.raises(CircuitBreakerError, match="is OPEN"):
        await circuit_breaker.call(any_func)

    assert circuit_breaker.metrics.rejected_calls == 1


@pytest.mark.asyncio
async def test_circuit_transitions_to_half_open(circuit_breaker):
    """Test circuit transitions to HALF_OPEN after timeout."""
    async def failing_func():
        raise ValueError("test error")

    # Open the circuit
    for _ in range(circuit_breaker.config.failure_threshold):
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

    assert circuit_breaker.is_open

    # Wait for timeout
    await asyncio.sleep(circuit_breaker.config.timeout_seconds + 0.1)

    # Next call should transition to HALF_OPEN
    async def success_func():
        return "success"

    result = await circuit_breaker.call(success_func)
    assert result == "success"
    assert circuit_breaker.is_half_open


@pytest.mark.asyncio
async def test_circuit_closes_from_half_open(circuit_breaker):
    """Test circuit closes after success threshold in HALF_OPEN."""
    async def failing_func():
        raise ValueError("test error")

    # Open the circuit
    for _ in range(circuit_breaker.config.failure_threshold):
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

    # Wait and transition to HALF_OPEN
    await asyncio.sleep(circuit_breaker.config.timeout_seconds + 0.1)

    async def success_func():
        return "success"

    # Make successful calls up to success threshold
    for _ in range(circuit_breaker.config.success_threshold):
        await circuit_breaker.call(success_func)

    # Circuit should be closed again
    assert circuit_breaker.is_closed


@pytest.mark.asyncio
async def test_circuit_reopens_on_half_open_failure(circuit_breaker):
    """Test circuit reopens on failure in HALF_OPEN state."""
    async def failing_func():
        raise ValueError("test error")

    # Open the circuit
    for _ in range(circuit_breaker.config.failure_threshold):
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

    # Wait and transition to HALF_OPEN
    await asyncio.sleep(circuit_breaker.config.timeout_seconds + 0.1)

    # One successful call to enter HALF_OPEN
    async def success_func():
        return "success"
    await circuit_breaker.call(success_func)
    assert circuit_breaker.is_half_open

    # Now fail - should reopen circuit
    with pytest.raises(ValueError):
        await circuit_breaker.call(failing_func)

    assert circuit_breaker.is_open


@pytest.mark.asyncio
async def test_circuit_breaker_metrics(circuit_breaker):
    """Test circuit breaker metrics collection."""
    async def success_func():
        return "success"

    async def failing_func():
        raise ValueError("test error")

    # Make some calls
    await circuit_breaker.call(success_func)
    
    with pytest.raises(ValueError):
        await circuit_breaker.call(failing_func)

    metrics = circuit_breaker.get_metrics()
    assert metrics["name"] == "test"
    assert metrics["total_calls"] == 2
    assert metrics["successful_calls"] == 1
    assert metrics["failed_calls"] == 1
    assert metrics["state"] == "closed"


@pytest.mark.asyncio
async def test_manual_reset(circuit_breaker):
    """Test manual circuit breaker reset."""
    async def failing_func():
        raise ValueError("test error")

    # Open the circuit
    for _ in range(circuit_breaker.config.failure_threshold):
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

    assert circuit_breaker.is_open

    # Manually reset
    await circuit_breaker.reset()
    assert circuit_breaker.is_closed


@pytest.mark.asyncio
async def test_circuit_breaker_registry():
    """Test circuit breaker registry."""
    registry = CircuitBreakerRegistry()

    # Create breakers
    breaker1 = await registry.get_or_create("breaker1")
    breaker2 = await registry.get_or_create("breaker2")

    assert breaker1.name == "breaker1"
    assert breaker2.name == "breaker2"

    # Get existing breaker
    same_breaker = await registry.get_or_create("breaker1")
    assert same_breaker is breaker1

    # Get by name
    found = await registry.get("breaker1")
    assert found is breaker1

    # Get all metrics
    metrics = await registry.get_all_metrics()
    assert "breaker1" in metrics
    assert "breaker2" in metrics


@pytest.mark.asyncio
async def test_sync_function_call(circuit_breaker):
    """Test circuit breaker with synchronous function."""
    def sync_func():
        return "sync result"

    result = await circuit_breaker.call(sync_func)
    assert result == "sync result"


@pytest.mark.asyncio
async def test_state_transitions_recorded(circuit_breaker):
    """Test state transitions are recorded in metrics."""
    async def failing_func():
        raise ValueError("test error")

    # Open the circuit
    for _ in range(circuit_breaker.config.failure_threshold):
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

    metrics = circuit_breaker.get_metrics()
    assert "closed_to_open" in metrics["state_transitions"]
    assert metrics["state_transitions"]["closed_to_open"] == 1


@pytest.mark.asyncio
async def test_half_open_max_calls_limit(circuit_breaker):
    """Test HALF_OPEN state limits concurrent calls."""
    async def failing_func():
        raise ValueError("test error")

    # Open the circuit
    for _ in range(circuit_breaker.config.failure_threshold):
        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

    # Wait and transition to HALF_OPEN
    await asyncio.sleep(circuit_breaker.config.timeout_seconds + 0.1)

    async def slow_func():
        await asyncio.sleep(0.1)
        return "success"

    # Start max allowed calls
    tasks = [
        asyncio.create_task(circuit_breaker.call(slow_func))
        for _ in range(circuit_breaker.config.half_open_max_calls)
    ]

    # Try one more - should be rejected
    with pytest.raises(CircuitBreakerError, match="max calls reached"):
        await circuit_breaker.call(slow_func)

    # Wait for tasks to complete
    await asyncio.gather(*tasks)
