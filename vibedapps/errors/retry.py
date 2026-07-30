"""Retry logic with exponential backoff for transient errors.

This module provides a retry decorator that automatically retries operations
that fail with transient errors, using exponential backoff to avoid overwhelming
failing services.
"""

import asyncio
import functools
import logging
import random
from typing import Any, Callable, Optional, Tuple, Type

from vibedapps.errors.exceptions import TransientError

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        backoff_factor: float = 2.0,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        exceptions: Tuple[Type[Exception], ...] = (TransientError,)
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts (including initial attempt)
            backoff_factor: Multiplier for delay between retries (exponential backoff)
            initial_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay in seconds between retries
            jitter: Whether to add random jitter to delays to avoid thundering herd
            exceptions: Tuple of exception types that should trigger retries
        """
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.exceptions = exceptions
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt number.
        
        Args:
            attempt: The attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        # Calculate exponential backoff: initial_delay * (backoff_factor ^ attempt)
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled (random value between 0 and delay)
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay


def retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (TransientError,)
):
    """
    Decorator that retries a function with exponential backoff on transient errors.
    
    Args:
        max_attempts: Maximum number of retry attempts (including initial attempt)
        backoff_factor: Multiplier for delay between retries
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        jitter: Whether to add random jitter to delays
        exceptions: Tuple of exception types that should trigger retries
    
    Example:
        @retry(max_attempts=3, backoff_factor=2, exceptions=(LLMServiceError,))
        async def call_llm_service(prompt: str) -> str:
            return await llm_service.generate_completion(prompt)
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        backoff_factor=backoff_factor,
        initial_delay=initial_delay,
        max_delay=max_delay,
        jitter=jitter,
        exceptions=exceptions
    )
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    result = await func(*args, **kwargs)
                    
                    # Log successful retry if this wasn't the first attempt
                    if attempt > 0:
                        logger.info(
                            f"Retry successful for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_attempts": config.max_attempts
                            }
                        )
                    
                    return result
                    
                except config.exceptions as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        
                        logger.warning(
                            f"Transient error in {func.__name__}, retrying in {delay:.2f}s",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_attempts": config.max_attempts,
                                "delay_seconds": delay,
                                "error": str(e),
                                "error_type": type(e).__name__
                            }
                        )
                        
                        await asyncio.sleep(delay)
                    else:
                        # Final attempt failed
                        logger.error(
                            f"All retry attempts exhausted for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "max_attempts": config.max_attempts,
                                "error": str(e),
                                "error_type": type(e).__name__
                            }
                        )
                
                except Exception as e:
                    # Non-retryable exception, fail immediately
                    logger.error(
                        f"Non-retryable error in {func.__name__}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    )
                    raise
            
            # All retries exhausted, raise the last exception
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    # Log successful retry if this wasn't the first attempt
                    if attempt > 0:
                        logger.info(
                            f"Retry successful for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_attempts": config.max_attempts
                            }
                        )
                    
                    return result
                    
                except config.exceptions as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        
                        logger.warning(
                            f"Transient error in {func.__name__}, retrying in {delay:.2f}s",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_attempts": config.max_attempts,
                                "delay_seconds": delay,
                                "error": str(e),
                                "error_type": type(e).__name__
                            }
                        )
                        
                        import time
                        time.sleep(delay)
                    else:
                        # Final attempt failed
                        logger.error(
                            f"All retry attempts exhausted for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "max_attempts": config.max_attempts,
                                "error": str(e),
                                "error_type": type(e).__name__
                            }
                        )
                
                except Exception as e:
                    # Non-retryable exception, fail immediately
                    logger.error(
                        f"Non-retryable error in {func.__name__}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    )
                    raise
            
            # All retries exhausted, raise the last exception
            raise last_exception
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RetryableOperation:
    """
    Context manager for retryable operations with custom retry logic.
    
    This provides more control than the decorator for cases where you need
    to customize retry behavior based on runtime conditions.
    
    Example:
        async with RetryableOperation(config) as retry_ctx:
            for attempt in retry_ctx:
                try:
                    result = await some_operation()
                    break
                except TransientError as e:
                    if not retry_ctx.should_retry(e):
                        raise
                    await retry_ctx.wait()
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retryable operation.
        
        Args:
            config: Retry configuration (uses defaults if not provided)
        """
        self.config = config or RetryConfig()
        self.attempt = 0
        self.last_exception = None
    
    def __iter__(self):
        """Iterate through retry attempts."""
        self.attempt = 0
        return self
    
    def __next__(self):
        """Get next retry attempt."""
        if self.attempt >= self.config.max_attempts:
            raise StopIteration
        
        current_attempt = self.attempt
        self.attempt += 1
        return current_attempt
    
    def should_retry(self, exception: Exception) -> bool:
        """
        Check if an exception should trigger a retry.
        
        Args:
            exception: The exception that occurred
        
        Returns:
            True if the exception is retryable and attempts remain
        """
        self.last_exception = exception
        
        # Check if exception type is retryable
        if not isinstance(exception, self.config.exceptions):
            return False
        
        # Check if we have attempts remaining
        return self.attempt < self.config.max_attempts
    
    async def wait(self):
        """Wait for the appropriate backoff delay."""
        delay = self.config.calculate_delay(self.attempt - 1)
        
        logger.warning(
            "Retrying operation after transient error",
            extra={
                "attempt": self.attempt,
                "max_attempts": self.config.max_attempts,
                "delay_seconds": delay,
                "error": str(self.last_exception),
                "error_type": type(self.last_exception).__name__
            }
        )
        
        await asyncio.sleep(delay)
