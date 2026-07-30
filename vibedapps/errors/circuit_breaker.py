"""
Circuit Breaker Pattern Implementation.

This module implements the circuit breaker pattern to prevent cascading failures
when external services (like LLM APIs) are experiencing issues. The circuit breaker
monitors failures and automatically "opens" to prevent further calls when a threshold
is reached, allowing the service time to recover.

Circuit States:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests fail immediately
- HALF_OPEN: Testing if service has recovered

Metrics tracked:
- Total calls
- Successful calls
- Failed calls
- Circuit state changes
- Time in each state
"""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

try:  # ParamSpec is in typing only on Python >= 3.10
    from typing import ParamSpec
except ImportError:  # Python 3.9 fallback
    from typing_extensions import ParamSpec
from functools import wraps

import structlog

from .exceptions import TransientError

logger = structlog.get_logger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejects a call."""
    
    def __init__(
        self,
        message: str = "Circuit breaker is open",
        service_name: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        """
        Initialize the circuit breaker open error.
        
        Args:
            message: Error message
            service_name: Name of the service protected by the circuit breaker
            retry_after: Seconds until the circuit breaker will attempt recovery
        """
        super().__init__(message)
        self.service_name = service_name
        self.retry_after = retry_after


class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""
    
    def __init__(self):
        """Initialize metrics."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rejected_calls = 0
        self.state_changes: Dict[str, int] = {
            CircuitState.CLOSED: 0,
            CircuitState.OPEN: 0,
            CircuitState.HALF_OPEN: 0
        }
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None
        self.current_state = CircuitState.CLOSED
        self.state_entered_at = time.time()
    
    def record_call(self):
        """Record a call attempt."""
        self.total_calls += 1
    
    def record_success(self):
        """Record a successful call."""
        self.successful_calls += 1
        self.last_success_time = time.time()
    
    def record_failure(self):
        """Record a failed call."""
        self.failed_calls += 1
        self.last_failure_time = time.time()
    
    def record_rejection(self):
        """Record a rejected call (circuit open)."""
        self.rejected_calls += 1
    
    def record_state_change(self, new_state: CircuitState):
        """Record a state change."""
        self.state_changes[new_state] += 1
        self.current_state = new_state
        self.state_entered_at = time.time()
    
    def get_failure_rate(self) -> float:
        """Calculate the failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls
    
    def get_time_in_current_state(self) -> float:
        """Get time spent in current state (seconds)."""
        return time.time() - self.state_entered_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "failure_rate": self.get_failure_rate(),
            "current_state": self.current_state,
            "time_in_current_state": self.get_time_in_current_state(),
            "state_changes": self.state_changes,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time
        }


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting external service calls.
    
    The circuit breaker monitors failures and automatically opens when a failure
    threshold is reached, preventing further calls to a failing service. After
    a timeout period, it enters a half-open state to test if the service has
    recovered.
    
    Example:
        ```python
        # Create a circuit breaker for LLM service
        llm_breaker = CircuitBreaker(
            name="llm_service",
            failure_threshold=5,
            timeout=60,
            expected_exceptions=(LLMServiceError,)
        )
        
        # Use with async function
        @llm_breaker
        async def call_llm(prompt: str) -> str:
            return await llm_service.generate(prompt)
        
        # Or call directly
        result = await llm_breaker.call(llm_service.generate, prompt)
        ```
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: int = 60,
        half_open_max_calls: int = 1,
        expected_exceptions: tuple = (TransientError,)
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            name: Name of the circuit breaker (for logging/metrics)
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting recovery (half-open)
            half_open_max_calls: Max calls to allow in half-open state
            expected_exceptions: Exceptions that should trigger the circuit breaker
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exceptions = expected_exceptions
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        
        self.metrics = CircuitBreakerMetrics()
        
        logger.info(
            "circuit_breaker_initialized",
            name=name,
            failure_threshold=failure_threshold,
            timeout=timeout
        )
    
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
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return False
        
        time_since_failure = time.time() - self._last_failure_time
        return time_since_failure >= self.timeout
    
    async def _transition_to_open(self):
        """Transition circuit to open state."""
        async with self._lock:
            if self._state != CircuitState.OPEN:
                old_state = self._state
                self._state = CircuitState.OPEN
                self._last_failure_time = time.time()
                self.metrics.record_state_change(CircuitState.OPEN)
                
                logger.warning(
                    "circuit_breaker_opened",
                    name=self.name,
                    previous_state=old_state,
                    failure_count=self._failure_count,
                    timeout=self.timeout
                )
    
    async def _transition_to_half_open(self):
        """Transition circuit to half-open state."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self.metrics.record_state_change(CircuitState.HALF_OPEN)
                
                logger.info(
                    "circuit_breaker_half_opened",
                    name=self.name,
                    max_test_calls=self.half_open_max_calls
                )
    
    async def _transition_to_closed(self):
        """Transition circuit to closed state."""
        async with self._lock:
            if self._state != CircuitState.CLOSED:
                old_state = self._state
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
                self.metrics.record_state_change(CircuitState.CLOSED)
                
                logger.info(
                    "circuit_breaker_closed",
                    name=self.name,
                    previous_state=old_state
                )
    
    async def _on_success(self):
        """Handle successful call."""
        self.metrics.record_success()
        
        if self._state == CircuitState.HALF_OPEN:
            # Success in half-open state, close the circuit
            await self._transition_to_closed()
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            async with self._lock:
                self._failure_count = 0
    
    async def _on_failure(self, exception: Exception):
        """Handle failed call."""
        self.metrics.record_failure()
        
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
        
        logger.warning(
            "circuit_breaker_failure",
            name=self.name,
            state=self._state,
            failure_count=self._failure_count,
            exception=str(exception)
        )
        
        if self._state == CircuitState.HALF_OPEN:
            # Failure in half-open state, reopen the circuit
            await self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            # Check if we've hit the failure threshold
            if self._failure_count >= self.failure_threshold:
                await self._transition_to_open()
    
    async def call(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: The function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            The result of the function call
        
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception raised by the function
        """
        # Check if we should attempt reset
        if self._state == CircuitState.OPEN and self._should_attempt_reset():
            await self._transition_to_half_open()
        
        # Reject call if circuit is open
        if self._state == CircuitState.OPEN:
            self.metrics.record_rejection()
            retry_after = int(self.timeout - (time.time() - self._last_failure_time))
            
            logger.warning(
                "circuit_breaker_rejected_call",
                name=self.name,
                retry_after=retry_after
            )
            
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open",
                service_name=self.name,
                retry_after=max(0, retry_after)
            )
        
        # Limit calls in half-open state
        if self._state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    self.metrics.record_rejection()
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is testing recovery, please retry later",
                        service_name=self.name,
                        retry_after=5
                    )
                self._half_open_calls += 1
        
        # Execute the call
        self.metrics.record_call()
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exceptions as e:
            await self._on_failure(e)
            raise
        except Exception as e:
            # Unexpected exception, don't count towards circuit breaker
            logger.error(
                "circuit_breaker_unexpected_exception",
                name=self.name,
                exception=str(e),
                exception_type=type(e).__name__
            )
            raise
    
    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        """
        Decorator to wrap a function with circuit breaker protection.
        
        Args:
            func: The function to wrap
        
        Returns:
            Wrapped function with circuit breaker protection
        """
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await self.call(func, *args, **kwargs)
        
        return wrapper
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        return {
            "name": self.name,
            "state": self._state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "timeout": self.timeout,
            **self.metrics.to_dict()
        }
    
    async def reset(self):
        """Manually reset the circuit breaker to closed state."""
        await self._transition_to_closed()
        logger.info("circuit_breaker_manually_reset", name=self.name)


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    
    This allows centralized management and monitoring of all circuit breakers
    in the system.
    """
    
    def __init__(self):
        """Initialize the registry."""
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def register(self, breaker: CircuitBreaker):
        """
        Register a circuit breaker.
        
        Args:
            breaker: The circuit breaker to register
        """
        async with self._lock:
            self._breakers[breaker.name] = breaker
            logger.info("circuit_breaker_registered", name=breaker.name)
    
    async def get(self, name: str) -> Optional[CircuitBreaker]:
        """
        Get a circuit breaker by name.
        
        Args:
            name: Name of the circuit breaker
        
        Returns:
            The circuit breaker, or None if not found
        """
        return self._breakers.get(name)
    
    async def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics for all circuit breakers.
        
        Returns:
            Dictionary mapping breaker names to their metrics
        """
        return {
            name: breaker.get_metrics()
            for name, breaker in self._breakers.items()
        }
    
    async def reset_all(self):
        """Reset all circuit breakers to closed state."""
        for breaker in self._breakers.values():
            await breaker.reset()
        logger.info("all_circuit_breakers_reset")


# Global registry instance
_registry = CircuitBreakerRegistry()


async def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    return _registry
