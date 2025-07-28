"""OpenAI provider adapter."""

import os
from typing import Dict, Any
import logging
from .base import BaseProvider, RateLimitError, APIError, LLMError

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI API provider adapter."""
    
    def __init__(self, api_key: str = None):
        """Initialize OpenAI provider."""
        super().__init__(api_key or os.getenv('OPENAI_API_KEY'))
        self.client = None
        
        if self.api_key:
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.debug("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI library not installed")
    
    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        return self.api_key is not None and self.client is not None
    
    def validate_model(self, model: str) -> bool:
        """Validate OpenAI model."""
        valid_models = [
            'gpt-4o', 'gpt-4o-mini', 'gpt-4', 'gpt-4-turbo',
            'gpt-3.5-turbo', 'gpt-3.5-turbo-16k'
        ]
        return model in valid_models
    
    def get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for OpenAI."""
        return {
            'temperature': 0.7,
            'max_tokens': 1000,
            'top_p': 1.0,
            'frequency_penalty': 0.0,
            'presence_penalty': 0.0
        }
    
    def query_model(self, model: str, prompt: str, **kwargs) -> str:
        """Query OpenAI model."""
        if not self.is_available():
            raise LLMError("OpenAI provider not available")
        
        if not self.validate_model(model):
            raise LLMError(f"Invalid OpenAI model: {model}")
        
        # Merge parameters
        params = self.get_default_params()
        params.update(kwargs)
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get('temperature', 0.7),
                max_tokens=params.get('max_tokens', 1000),
                top_p=params.get('top_p', 1.0),
                frequency_penalty=params.get('frequency_penalty', 0.0),
                presence_penalty=params.get('presence_penalty', 0.0)
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.handle_error(e, model)
    
    def handle_error(self, error: Exception, model: str) -> None:
        """Handle OpenAI-specific errors."""
        error_msg = str(error).lower()
        
        # OpenAI specific rate limit errors
        if 'rate_limit_exceeded' in error_msg or 'quota_exceeded' in error_msg:
            raise RateLimitError(f"OpenAI rate limit exceeded for {model}: {error}")
        
        # OpenAI API errors
        if any(term in error_msg for term in ['invalid_request_error', 'authentication_error', 'permission_error']):
            raise APIError(f"OpenAI API error for {model}: {error}")
        
        # Fall back to base error handling
        super().handle_error(error, model)