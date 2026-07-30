import json
import logging
import os
from typing import Any, Dict, List, Optional

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI
from openai import RateLimitError as OpenAIRateLimitError

from vibedapps.errors.circuit_breaker import (
    CircuitBreaker,
    get_circuit_breaker_registry,
)
from vibedapps.errors.exceptions import LLMServiceError
from vibedapps.errors.retry import retry

logger = logging.getLogger(__name__)


# Default circuit breaker configuration for LLM service
DEFAULT_LLM_CIRCUIT_BREAKER_CONFIG = {
    "failure_threshold": 5,  # Open after 5 consecutive failures
    "timeout": 60,  # Wait 60 seconds before half-open
    "half_open_max_calls": 1,  # Allow 1 test call in half-open state
}


class OpenAIService:
    """
    Service for interacting with OpenAI models.

    Features:
    - Automatic retry with exponential backoff for transient errors
    - Circuit breaker pattern to prevent cascading failures
    - Configurable circuit breaker thresholds
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        circuit_breaker_config: Optional[Dict[str, Any]] = None,
        enable_circuit_breaker: bool = True
    ):
        """
        Initialize the OpenAI service.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            circuit_breaker_config: Configuration for circuit breaker (optional)
            enable_circuit_breaker: Whether to enable circuit breaker (default: True)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key)

        # Initialize circuit breaker
        self.enable_circuit_breaker = enable_circuit_breaker
        if enable_circuit_breaker:
            cb_config = circuit_breaker_config or DEFAULT_LLM_CIRCUIT_BREAKER_CONFIG
            self._completion_circuit_breaker = CircuitBreaker(
                name="openai_completion",
                failure_threshold=cb_config.get("failure_threshold", 5),
                timeout=cb_config.get("timeout", 60),
                half_open_max_calls=cb_config.get("half_open_max_calls", 1),
                expected_exceptions=(LLMServiceError,)
            )
            self._embedding_circuit_breaker = CircuitBreaker(
                name="openai_embedding",
                failure_threshold=cb_config.get("failure_threshold", 5),
                timeout=cb_config.get("timeout", 60),
                half_open_max_calls=cb_config.get("half_open_max_calls", 1),
                expected_exceptions=(LLMServiceError,)
            )
            logger.info(
                "OpenAI service initialized with circuit breaker",
                extra=cb_config
            )
        else:
            self._completion_circuit_breaker = None
            self._embedding_circuit_breaker = None
            logger.info("OpenAI service initialized without circuit breaker")

    async def register_circuit_breakers(self) -> None:
        """Register circuit breakers with the global registry."""
        if self.enable_circuit_breaker:
            registry = await get_circuit_breaker_registry()
            if self._completion_circuit_breaker:
                await registry.register(self._completion_circuit_breaker)
            if self._embedding_circuit_breaker:
                await registry.register(self._embedding_circuit_breaker)
            logger.info("LLM circuit breakers registered with global registry")

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get the current status of circuit breakers."""
        status = {"enabled": self.enable_circuit_breaker}
        if self._completion_circuit_breaker:
            status["completion"] = self._completion_circuit_breaker.get_metrics()
        if self._embedding_circuit_breaker:
            status["embedding"] = self._embedding_circuit_breaker.get_metrics()
        return status

    async def reset_circuit_breakers(self) -> None:
        """Manually reset circuit breakers to closed state."""
        if self._completion_circuit_breaker:
            await self._completion_circuit_breaker.reset()
        if self._embedding_circuit_breaker:
            await self._embedding_circuit_breaker.reset()
        logger.info("LLM circuit breakers manually reset")

    async def generate_completion(
            self,
            messages: List[Dict[str, str]],
            model: str = "gpt-4o",
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            tools: Optional[List[Dict[str, Any]]] = None,
            tool_choice: Optional[str] = None,
    ) -> str:
        """
        Generate a completion from the LLM with circuit breaker and retry protection.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: OpenAI model to use
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            tools: Optional list of tool definitions
            tool_choice: Optional tool choice strategy

        Returns:
            Generated completion text or JSON with tool calls

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            LLMServiceError: On transient errors (retried automatically)
            Exception: On permanent errors (not retried)
        """
        # Use circuit breaker if enabled
        if self._completion_circuit_breaker:
            return await self._completion_circuit_breaker.call(
                self._generate_completion_internal,
                messages, model, temperature, max_tokens, tools, tool_choice
            )
        else:
            return await self._generate_completion_internal(
                messages, model, temperature, max_tokens, tools, tool_choice
            )

    @retry(
        max_attempts=3,
        backoff_factor=2.0,
        initial_delay=1.0,
        max_delay=60.0,
        exceptions=(LLMServiceError,)
    )
    async def _generate_completion_internal(
            self,
            messages: List[Dict[str, str]],
            model: str = "gpt-4o",
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            tools: Optional[List[Dict[str, Any]]] = None,
            tool_choice: Optional[str] = None,
    ) -> str:
        """Internal method to generate completion with retry logic."""
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }

            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            if tools:
                kwargs["tools"] = tools
                if tool_choice:
                    kwargs["tool_choice"] = tool_choice

            logger.debug(
                "Calling OpenAI API",
                extra={
                    "model": model,
                    "message_count": len(messages),
                    "temperature": temperature
                }
            )

            response = await self.client.chat.completions.create(**kwargs)

            # Handle tool calls if present
            if response.choices[0].message.tool_calls:
                return json.dumps({
                    "content": response.choices[0].message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        }
                        for tool_call in response.choices[0].message.tool_calls
                    ]
                })

            return response.choices[0].message.content or ""

        except OpenAIRateLimitError as e:
            # Rate limit errors are transient and should be retried
            logger.warning(
                "OpenAI rate limit exceeded",
                extra={"error": str(e)}
            )
            raise LLMServiceError(
                message="OpenAI rate limit exceeded",
                status_code=429,
                cause=e
            )

        except APITimeoutError as e:
            # Timeout errors are transient and should be retried
            logger.warning(
                "OpenAI API timeout",
                extra={"error": str(e)}
            )
            raise LLMServiceError(
                message="OpenAI API timeout",
                status_code=504,
                cause=e
            )

        except APIConnectionError as e:
            # Non-timeout connection failures are transient and should be retried
            logger.warning(
                "OpenAI API connection error",
                extra={"error": str(e)}
            )
            raise LLMServiceError(
                message="OpenAI API connection error",
                status_code=503,
                cause=e
            )

        except APIError as e:
            # Check if this is a transient error (5xx status codes)
            if hasattr(e, 'status_code') and 500 <= e.status_code < 600:
                logger.warning(
                    "OpenAI API server error",
                    extra={"error": str(e), "status_code": e.status_code}
                )
                raise LLMServiceError(
                    message=f"OpenAI API server error: {str(e)}",
                    status_code=e.status_code,
                    cause=e
                )
            else:
                # Permanent error (4xx), don't retry
                logger.error(
                    "OpenAI API client error",
                    extra={"error": str(e), "status_code": getattr(e, 'status_code', None)}
                )
                raise

        except Exception as e:
            # Unknown error, log and re-raise
            logger.error(
                "Unexpected error calling OpenAI API",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise

    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-ada-002"
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts with circuit breaker and retry protection.

        Args:
            texts: List of text strings to embed
            model: OpenAI embedding model to use

        Returns:
            List of embedding vectors

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            LLMServiceError: On transient errors (retried automatically)
            Exception: On permanent errors (not retried)
        """
        # Use circuit breaker if enabled
        if self._embedding_circuit_breaker:
            return await self._embedding_circuit_breaker.call(
                self._generate_embeddings_internal,
                texts, model
            )
        else:
            return await self._generate_embeddings_internal(texts, model)

    @retry(
        max_attempts=3,
        backoff_factor=2.0,
        initial_delay=1.0,
        max_delay=60.0,
        exceptions=(LLMServiceError,)
    )
    async def _generate_embeddings_internal(
        self,
        texts: List[str],
        model: str = "text-embedding-ada-002"
    ) -> List[List[float]]:
        """Internal method to generate embeddings with retry logic."""
        try:
            logger.debug(
                "Generating embeddings",
                extra={
                    "model": model,
                    "text_count": len(texts)
                }
            )

            response = await self.client.embeddings.create(
                model=model,
                input=texts
            )
            return [item.embedding for item in response.data]

        except OpenAIRateLimitError as e:
            logger.warning(
                "OpenAI rate limit exceeded for embeddings",
                extra={"error": str(e)}
            )
            raise LLMServiceError(
                message="OpenAI rate limit exceeded",
                status_code=429,
                cause=e
            )

        except APITimeoutError as e:
            logger.warning(
                "OpenAI API timeout for embeddings",
                extra={"error": str(e)}
            )
            raise LLMServiceError(
                message="OpenAI API timeout",
                status_code=504,
                cause=e
            )

        except APIConnectionError as e:
            # Non-timeout connection failures are transient and should be retried
            logger.warning(
                "OpenAI API connection error for embeddings",
                extra={"error": str(e)}
            )
            raise LLMServiceError(
                message="OpenAI API connection error",
                status_code=503,
                cause=e
            )

        except APIError as e:
            if hasattr(e, 'status_code') and 500 <= e.status_code < 600:
                logger.warning(
                    "OpenAI API server error for embeddings",
                    extra={"error": str(e), "status_code": e.status_code}
                )
                raise LLMServiceError(
                    message=f"OpenAI API server error: {str(e)}",
                    status_code=e.status_code,
                    cause=e
                )
            else:
                logger.error(
                    "OpenAI API client error for embeddings",
                    extra={"error": str(e), "status_code": getattr(e, 'status_code', None)}
                )
                raise

        except Exception as e:
            logger.error(
                "Unexpected error generating embeddings",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise