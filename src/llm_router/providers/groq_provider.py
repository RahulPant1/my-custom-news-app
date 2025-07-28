"""Groq provider adapter."""

import os
from typing import Dict, Any
import logging
from .base import BaseProvider, RateLimitError, APIError, LLMError

logger = logging.getLogger(__name__)


class GroqProvider(BaseProvider):
    """Groq API provider adapter."""
    
    def __init__(self, api_key: str = None):
        """Initialize Groq provider."""
        super().__init__(api_key or os.getenv('GROQ_API_KEY'))
        self.client = None
        
        if self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                logger.debug("Groq client initialized")
            except ImportError:
                logger.warning("Groq library not installed")
    
    def is_available(self) -> bool:
        """Check if Groq is available."""
        return self.api_key is not None and self.client is not None
    
    def validate_model(self, model: str) -> bool:
        """Validate Groq model."""
        valid_models = [
            'llama-3.1-70b-versatile', 'llama-3.1-8b-instant',
            'llama-3.2-90b-text-preview', 'llama-3.2-11b-text-preview',
            'llama-3.3-70b-versatile', 'llama-3.3-70b-specdec',
            'deepseek-r1-distill-llama-70b', 'deepseek-r1-distill-qwen-32b',
            'mixtral-8x7b-32768', 'gemma-7b-it'
        ]
        return model in valid_models
    
    def get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for Groq."""
        return {
            'temperature': 0.7,
            'max_tokens': 1000,
            'top_p': 1.0
        }
    
    def query_model(self, model: str, prompt: str, **kwargs) -> str:
        """Query Groq model."""
        if not self.is_available():
            raise LLMError("Groq provider not available")
        
        if not self.validate_model(model):
            raise LLMError(f"Invalid Groq model: {model}")
        
        # Merge parameters
        params = self.get_default_params()
        params.update(kwargs)
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get('temperature', 0.7),
                max_tokens=params.get('max_tokens', 1000),
                top_p=params.get('top_p', 1.0)
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.handle_error(e, model)
    
    def handle_error(self, error: Exception, model: str) -> None:
        """Handle Groq-specific errors."""
        error_msg = str(error).lower()
        
        # Groq specific rate limit errors
        if 'rate limit' in error_msg or 'too many requests' in error_msg:
            raise RateLimitError(f"Groq rate limit exceeded for {model}: {error}")
        
        # Groq API errors
        if any(term in error_msg for term in ['invalid_request', 'authentication', 'insufficient_quota']):
            raise APIError(f"Groq API error for {model}: {error}")
        
        # Fall back to base error handling
        super().handle_error(error, model)