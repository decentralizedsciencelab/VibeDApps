"""Custom exception hierarchy for the DApp Generator System.

This module defines a comprehensive exception hierarchy that categorizes errors
into transient (retryable) and permanent (non-retryable) errors, enabling
intelligent error handling and retry logic throughout the system.
"""

from typing import Any, Dict, Optional


class DAppGeneratorError(Exception):
    """
    Base exception for all DApp Generator system errors.
    
    All custom exceptions in the system should inherit from this class.
    This allows for catching all system-specific errors with a single except clause.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        Initialize the error.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (e.g., "CONTRACT_GENERATION_FAILED")
            details: Additional error details for debugging
            cause: The underlying exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the error to a dictionary for API responses."""
        error_dict = {
            "code": self.error_code,
            "message": self.message,
        }
        
        if self.details:
            error_dict["details"] = self.details
        
        if self.cause:
            error_dict["cause"] = str(self.cause)
        
        return error_dict


# ============================================================================
# TRANSIENT ERRORS (Retryable)
# ============================================================================

class TransientError(DAppGeneratorError):
    """
    Base class for transient errors that can be retried.
    
    These errors are typically caused by temporary issues like network problems,
    service unavailability, or rate limiting. They should be retried with
    exponential backoff.
    """
    pass


class LLMServiceError(TransientError):
    """
    Error communicating with the LLM service (OpenAI API).
    
    This can occur due to:
    - Network connectivity issues
    - API rate limiting
    - Service unavailability
    - Timeout errors
    """
    
    def __init__(
        self,
        message: str = "LLM service error",
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the LLM service error.
        
        Args:
            message: Error message
            status_code: HTTP status code from the API
            retry_after: Seconds to wait before retrying (from Retry-After header)
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="LLM_SERVICE_ERROR", **kwargs)
        self.status_code = status_code
        self.retry_after = retry_after
        
        if status_code:
            self.details["status_code"] = status_code
        if retry_after:
            self.details["retry_after"] = retry_after


class AgentCommunicationError(TransientError):
    """
    Error communicating between agents.
    
    This can occur when:
    - An agent is temporarily unavailable
    - Network issues prevent agent communication
    - Agent response timeout
    """
    
    def __init__(
        self,
        message: str = "Agent communication error",
        agent_name: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the agent communication error.
        
        Args:
            message: Error message
            agent_name: Name of the agent that failed to communicate
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="AGENT_COMMUNICATION_ERROR", **kwargs)
        self.agent_name = agent_name
        
        if agent_name:
            self.details["agent_name"] = agent_name


class DatabaseError(TransientError):
    """
    Error interacting with the database.
    
    This can occur due to:
    - Connection pool exhaustion
    - Temporary network issues
    - Database server overload
    - Deadlocks or lock timeouts
    """
    
    def __init__(
        self,
        message: str = "Database error",
        operation: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the database error.
        
        Args:
            message: Error message
            operation: The database operation that failed (e.g., "insert", "query")
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="DATABASE_ERROR", **kwargs)
        self.operation = operation
        
        if operation:
            self.details["operation"] = operation


class CacheError(TransientError):
    """
    Error interacting with the cache (Redis).
    
    This can occur due to:
    - Redis connection issues
    - Cache server unavailability
    - Network problems
    """
    
    def __init__(
        self,
        message: str = "Cache error",
        operation: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the cache error.
        
        Args:
            message: Error message
            operation: The cache operation that failed (e.g., "get", "set")
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="CACHE_ERROR", **kwargs)
        self.operation = operation
        
        if operation:
            self.details["operation"] = operation


# ============================================================================
# PERMANENT ERRORS (Non-retryable)
# ============================================================================

class PermanentError(DAppGeneratorError):
    """
    Base class for permanent errors that should not be retried.
    
    These errors are typically caused by invalid input, missing resources,
    or configuration issues. Retrying these errors will not help.
    """
    pass


class ValidationError(PermanentError):
    """
    Error validating user input or data.
    
    This occurs when:
    - Required fields are missing
    - Field values are invalid
    - Data format is incorrect
    - Business rules are violated
    """
    
    def __init__(
        self,
        message: str = "Validation error",
        field: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the validation error.
        
        Args:
            message: Error message
            field: The field that failed validation
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)
        self.field = field
        
        if field:
            self.details["field"] = field


class AuthenticationError(PermanentError):
    """
    Error authenticating a user or request.
    
    This occurs when:
    - API key is missing or invalid
    - JWT token is expired or invalid
    - Credentials are incorrect
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        **kwargs
    ):
        """Initialize the authentication error."""
        super().__init__(message, error_code="AUTHENTICATION_ERROR", **kwargs)


class AuthorizationError(PermanentError):
    """
    Error authorizing a user or request.
    
    This occurs when:
    - User lacks required permissions
    - Resource access is forbidden
    - Operation is not allowed for the user
    """
    
    def __init__(
        self,
        message: str = "Authorization failed",
        resource: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the authorization error.
        
        Args:
            message: Error message
            resource: The resource that access was denied to
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="AUTHORIZATION_ERROR", **kwargs)
        self.resource = resource
        
        if resource:
            self.details["resource"] = resource


class RateLimitError(PermanentError):
    """
    Error when rate limit is exceeded.
    
    This occurs when a user exceeds their allowed request rate.
    While technically transient (will succeed after waiting), we treat
    it as permanent to avoid automatic retries that would continue to
    hit the rate limit.
    """
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        limit: Optional[int] = None,
        window: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
            limit: The rate limit that was exceeded
            window: The time window for the rate limit (in seconds)
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED", **kwargs)
        self.retry_after = retry_after
        self.limit = limit
        self.window = window
        
        if retry_after:
            self.details["retry_after"] = retry_after
        if limit:
            self.details["limit"] = limit
        if window:
            self.details["window"] = window


class ResourceNotFoundError(PermanentError):
    """
    Error when a requested resource is not found.
    
    This occurs when:
    - Project ID doesn't exist
    - File is not found
    - Agent is not registered
    """
    
    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the resource not found error.
        
        Args:
            message: Error message
            resource_type: Type of resource (e.g., "project", "file")
            resource_id: ID of the resource that was not found
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="RESOURCE_NOT_FOUND", **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id
        
        if resource_type:
            self.details["resource_type"] = resource_type
        if resource_id:
            self.details["resource_id"] = resource_id


class ResourceExhaustedError(PermanentError):
    """
    Error when a resource limit is exhausted.
    
    This occurs when:
    - Disk quota is exceeded
    - Memory limit is reached
    - Maximum project count is exceeded
    """
    
    def __init__(
        self,
        message: str = "Resource exhausted",
        resource_type: Optional[str] = None,
        limit: Optional[Any] = None,
        current: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize the resource exhausted error.
        
        Args:
            message: Error message
            resource_type: Type of resource (e.g., "disk", "memory")
            limit: The resource limit
            current: Current resource usage
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="RESOURCE_EXHAUSTED", **kwargs)
        self.resource_type = resource_type
        self.limit = limit
        self.current = current
        
        if resource_type:
            self.details["resource_type"] = resource_type
        if limit is not None:
            self.details["limit"] = limit
        if current is not None:
            self.details["current"] = current


class ConfigurationError(PermanentError):
    """
    Error in system configuration.
    
    This occurs when:
    - Required environment variables are missing
    - Configuration values are invalid
    - Service dependencies are not configured
    """
    
    def __init__(
        self,
        message: str = "Configuration error",
        config_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the configuration error.
        
        Args:
            message: Error message
            config_key: The configuration key that is invalid
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, error_code="CONFIGURATION_ERROR", **kwargs)
        self.config_key = config_key
        
        if config_key:
            self.details["config_key"] = config_key


# ============================================================================
# GENERATION ERRORS (Can be transient or permanent depending on cause)
# ============================================================================

class GenerationError(DAppGeneratorError):
    """
    Base class for errors during DApp generation.
    
    These errors can be either transient or permanent depending on the
    underlying cause. The specific subclass and cause should be examined
    to determine if retry is appropriate.
    """
    
    def __init__(
        self,
        message: str,
        stage: Optional[str] = None,
        is_transient: bool = False,
        **kwargs
    ):
        """
        Initialize the generation error.
        
        Args:
            message: Error message
            stage: The generation stage that failed
            is_transient: Whether this error is transient and can be retried
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(message, **kwargs)
        self.stage = stage
        self.is_transient = is_transient
        
        if stage:
            self.details["stage"] = stage
        self.details["is_transient"] = is_transient


class ContractGenerationError(GenerationError):
    """Error during smart contract generation."""
    
    def __init__(self, message: str = "Contract generation failed", **kwargs):
        """Initialize the contract generation error."""
        super().__init__(
            message,
            error_code="CONTRACT_GENERATION_ERROR",
            stage="contract_generation",
            **kwargs
        )


class BackendGenerationError(GenerationError):
    """Error during backend code generation."""
    
    def __init__(self, message: str = "Backend generation failed", **kwargs):
        """Initialize the backend generation error."""
        super().__init__(
            message,
            error_code="BACKEND_GENERATION_ERROR",
            stage="backend_generation",
            **kwargs
        )


class FrontendGenerationError(GenerationError):
    """Error during frontend code generation."""
    
    def __init__(self, message: str = "Frontend generation failed", **kwargs):
        """Initialize the frontend generation error."""
        super().__init__(
            message,
            error_code="FRONTEND_GENERATION_ERROR",
            stage="frontend_generation",
            **kwargs
        )


class AuditError(GenerationError):
    """Error during smart contract audit."""
    
    def __init__(self, message: str = "Contract audit failed", **kwargs):
        """Initialize the audit error."""
        super().__init__(
            message,
            error_code="AUDIT_ERROR",
            stage="contract_audit",
            **kwargs
        )


class TestGenerationError(GenerationError):
    """Error during test generation."""
    
    def __init__(self, message: str = "Test generation failed", **kwargs):
        """Initialize the test generation error."""
        super().__init__(
            message,
            error_code="TEST_GENERATION_ERROR",
            stage="test_generation",
            **kwargs
        )


class IntegrationError(GenerationError):
    """Error during component integration."""
    
    def __init__(self, message: str = "Integration failed", **kwargs):
        """Initialize the integration error."""
        super().__init__(
            message,
            error_code="INTEGRATION_ERROR",
            stage="integration",
            **kwargs
        )


class PackagingError(GenerationError):
    """Error during project packaging."""
    
    def __init__(self, message: str = "Packaging failed", **kwargs):
        """Initialize the packaging error."""
        super().__init__(
            message,
            error_code="PACKAGING_ERROR",
            stage="packaging",
            **kwargs
        )
