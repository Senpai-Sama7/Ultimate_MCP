"""Circuit breaker pattern implementation for resilience."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures exceeded, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout_seconds: float = 60.0  # Time to wait before half-open
    half_open_max_calls: int = 3  # Max calls in half-open state


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_transitions: dict[str, int] = field(default_factory=dict)
    last_failure_time: float | None = None
    last_success_time: float | None = None


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance.
    
    Prevents cascading failures by temporarily blocking calls to failing services.
    States:
    - CLOSED: Normal operation, failures counted
    - OPEN: Too many failures, all calls rejected
    - HALF_OPEN: Testing recovery, limited calls allowed
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        """Initialize circuit breaker.
        
        Args:
            name: Identifier for this circuit breaker
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._opened_at: float | None = None
        self._half_open_calls = 0
        self._half_open_attempts = 0
        self._lock = asyncio.Lock()
        self.metrics = CircuitBreakerMetrics()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting calls)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> T:
        """Execute function through circuit breaker."""
        await asyncio.sleep(0)
        return await self._execute(func, *args, **kwargs)

    async def _execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> T:
        """Internal execution helper that enforces breaker semantics."""
        async with self._lock:
            self.metrics.total_calls += 1
            
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self.metrics.rejected_calls += 1
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Last failure: {self._last_failure_time}"
                    )
            
            # In HALF_OPEN, limit concurrent calls
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_attempts >= self.config.half_open_max_calls:
                    self.metrics.rejected_calls += 1
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN "
                        f"with max calls reached"
                    )
                self._half_open_attempts += 1
                self._half_open_calls += 1

        # Execute the function outside the lock
        if asyncio.iscoroutinefunction(func):
            try:
                result = await func(*args, **kwargs)
            except Exception as exc:
                await self._on_failure(exc)
                raise
        else:
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                await self._on_failure(exc)
                raise

        await self._on_success()
        return result

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self.metrics.successful_calls += 1
            self.metrics.last_success_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls > 0:
                    self._half_open_calls -= 1
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            else:
                # Reset failure count on success in CLOSED state
                self._failure_count = 0

    async def _on_failure(self, exception: Exception) -> None:
        """Handle failed call."""
        async with self._lock:
            self.metrics.failed_calls += 1
            self._last_failure_time = time.time()
            self.metrics.last_failure_time = self._last_failure_time
            
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN immediately opens circuit
                self._half_open_calls -= 1
                self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to_open()
            
            logger.warning(
                f"Circuit breaker '{self.name}' recorded failure",
                extra={
                    "state": self._state.value,
                    "failure_count": self._failure_count,
                    "exception": str(exception),
                },
            )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._opened_at is None:
            return True
        return (time.time() - self._opened_at) >= self.config.timeout_seconds

    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        previous_state = self._state
        self._state = CircuitState.OPEN
        self._opened_at = time.time()
        self._record_transition(previous_state, CircuitState.OPEN)
        logger.warning(
            f"Circuit breaker '{self.name}' opened",
            extra={
                "previous_state": previous_state.value,
                "failure_count": self._failure_count,
            },
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        previous_state = self._state
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._half_open_calls = 0
        self._half_open_attempts = 0
        self._record_transition(previous_state, CircuitState.HALF_OPEN)
        logger.info(
            f"Circuit breaker '{self.name}' entered HALF_OPEN state",
            extra={"previous_state": previous_state.value},
        )

    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        previous_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        self._half_open_calls = 0
        self._half_open_attempts = 0
        self._record_transition(previous_state, CircuitState.CLOSED)
        logger.info(
            f"Circuit breaker '{self.name}' closed",
            extra={"previous_state": previous_state.value},
        )

    def _record_transition(
        self,
        from_state: CircuitState,
        to_state: CircuitState,
    ) -> None:
        """Record state transition in metrics."""
        transition_key = f"{from_state.value}_to_{to_state.value}"
        self.metrics.state_transitions[transition_key] = (
            self.metrics.state_transitions.get(transition_key, 0) + 1
        )

    async def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        async with self._lock:
            self._transition_to_closed()

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            "name": self.name,
            "state": self._state.value,
            "total_calls": self.metrics.total_calls,
            "successful_calls": self.metrics.successful_calls,
            "failed_calls": self.metrics.failed_calls,
            "rejected_calls": self.metrics.rejected_calls,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "state_transitions": dict(self.metrics.state_transitions),
            "last_failure_time": self.metrics.last_failure_time,
            "last_success_time": self.metrics.last_success_time,
            "opened_at": self._opened_at,
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        """Initialize circuit breaker registry."""
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker.
        
        Args:
            name: Circuit breaker name
            config: Configuration for new breaker
            
        Returns:
            Circuit breaker instance
        """
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    async def get(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name.
        
        Args:
            name: Circuit breaker name
            
        Returns:
            Circuit breaker instance or None
        """
        async with self._lock:
            return self._breakers.get(name)

    async def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all circuit breakers.
        
        Returns:
            Dictionary mapping breaker name to metrics
        """
        async with self._lock:
            return {
                name: breaker.get_metrics()
                for name, breaker in self._breakers.items()
            }

    async def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state."""
        async with self._lock:
            for breaker in self._breakers.values():
                await breaker.reset()


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerMetrics",
    "CircuitBreakerRegistry",
    "CircuitState",
]
