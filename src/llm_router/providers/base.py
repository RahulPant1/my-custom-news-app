"""Base provider interface for LLM adapters."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class RateLimitError(LLMError):
    """Raised when rate limits are exceeded."""
    pass


class APIError(LLMError):
    """Raised when API calls fail."""
    pass


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize provider with API key."""
        self.api_key = api_key
        self.name = self.__class__.__name__.replace('Provider', '').lower()
    
    @abstractmethod
    def query_model(self, model: str, prompt: str, **kwargs) -> str:
        """
        Query the specified model with a prompt.
        
        Args:
            model: Model identifier
            prompt: Text prompt to send
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            str: Model response text
            
        Raises:
            RateLimitError: When rate limits are exceeded
            APIError: When API calls fail
            LLMError: For other provider-specific errors
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available (has API key, etc.)."""
        pass
    
    def validate_model(self, model: str) -> bool:
        """
        Validate if model is supported by this provider.
        Override in subclasses to implement model validation.
        """
        return True
    
    def get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for this provider."""
        return {
            'temperature': 0.7,
            'max_tokens': 1000
        }
    
    def handle_error(self, error: Exception, model: str) -> None:
        """
        Handle and classify errors from provider APIs.
        Override in subclasses for provider-specific error handling.
        """
        error_msg = str(error).lower()
        
        # Common rate limit indicators
        if any(term in error_msg for term in ['rate limit', 'quota', 'too many requests']):
            raise RateLimitError(f"Rate limit exceeded for {model}: {error}")
        
        # Common API errors
        if any(term in error_msg for term in ['api', 'service', 'server', 'timeout']):
            raise APIError(f"API error for {model}: {error}")
        
        # Generic LLM error
        raise LLMError(f"LLM error for {model}: {error}")