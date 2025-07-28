"""Anthropic Claude provider adapter."""

import os
from typing import Dict, Any
import logging
from .base import BaseProvider, RateLimitError, APIError, LLMError

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API provider adapter."""
    
    def __init__(self, api_key: str = None):
        """Initialize Anthropic provider."""
        super().__init__(api_key or os.getenv('ANTHROPIC_API_KEY'))
        self.client = None
        
        if self.api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                logger.debug("Anthropic client initialized")
            except ImportError:
                logger.warning("Anthropic library not installed")
    
    def is_available(self) -> bool:
        """Check if Anthropic is available."""
        return self.api_key is not None and self.client is not None
    
    def validate_model(self, model: str) -> bool:
        """Validate Anthropic model."""
        valid_models = [
            'claude-3-5-sonnet-20241022', 'claude-3-sonnet-20240229', 'claude-3-opus-20240229',
            'claude-3-haiku-20240307', 'claude-instant-1.2'
        ]
        return model in valid_models
    
    def get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for Anthropic."""
        return {
            'temperature': 0.7,
            'max_tokens': 1000,
            'top_p': 1.0
        }
    
    def query_model(self, model: str, prompt: str, **kwargs) -> str:
        """Query Anthropic model."""
        if not self.is_available():
            raise LLMError("Anthropic provider not available")
        
        if not self.validate_model(model):
            raise LLMError(f"Invalid Anthropic model: {model}")
        
        # Merge parameters
        params = self.get_default_params()
        params.update(kwargs)
        
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=params.get('max_tokens', 1000),
                temperature=params.get('temperature', 0.7),
                top_p=params.get('top_p', 1.0),
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            self.handle_error(e, model)
    
    def handle_error(self, error: Exception, model: str) -> None:
        """Handle Anthropic-specific errors."""
        error_msg = str(error).lower()
        
        # Anthropic specific rate limit errors
        if 'rate_limit' in error_msg or 'usage_limit' in error_msg:
            raise RateLimitError(f"Anthropic rate limit exceeded for {model}: {error}")
        
        # Anthropic API errors  
        if any(term in error_msg for term in ['invalid_request', 'authentication', 'permission']):
            raise APIError(f"Anthropic API error for {model}: {error}")
        
        # Fall back to base error handling
        super().handle_error(error, model)