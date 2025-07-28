"""Google Gemini provider adapter."""

import os
from typing import Dict, Any
import logging
from .base import BaseProvider, RateLimitError, APIError, LLMError

logger = logging.getLogger(__name__)


class GoogleProvider(BaseProvider):
    """Google Gemini API provider adapter."""
    
    def __init__(self, api_key: str = None):
        """Initialize Google provider."""
        super().__init__(api_key or os.getenv('GOOGLE_API_KEY'))
        self.genai = None
        
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.genai = genai
                logger.debug("Google Gemini client initialized")
            except ImportError:
                logger.warning("Google Generative AI library not installed")
    
    def is_available(self) -> bool:
        """Check if Google Gemini is available."""
        return self.api_key is not None and self.genai is not None
    
    def validate_model(self, model: str) -> bool:
        """Validate Google model."""
        valid_models = [
            'gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-1.5-pro', 
            'gemini-1.5-flash', 'gemini-pro', 'gemini-pro-vision'
        ]
        return model in valid_models
    
    def get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for Google."""
        return {
            'temperature': 0.7,
            'top_p': 1.0,
            'top_k': 40,
            'max_output_tokens': 1000
        }
    
    def query_model(self, model: str, prompt: str, **kwargs) -> str:
        """Query Google Gemini model."""
        if not self.is_available():
            raise LLMError("Google provider not available")
        
        if not self.validate_model(model):
            raise LLMError(f"Invalid Google model: {model}")
        
        # Merge parameters
        params = self.get_default_params()
        params.update(kwargs)
        
        try:
            # Create generation config
            generation_config = {
                'temperature': params.get('temperature', 0.7),
                'top_p': params.get('top_p', 1.0),
                'top_k': params.get('top_k', 40),
                'max_output_tokens': params.get('max_output_tokens', 1000)
            }
            
            # Initialize model
            model_instance = self.genai.GenerativeModel(
                model_name=model,
                generation_config=generation_config
            )
            
            # Generate response
            response = model_instance.generate_content(prompt)
            
            if response.text:
                return response.text.strip()
            else:
                raise LLMError(f"Empty response from Google model {model}")
            
        except Exception as e:
            self.handle_error(e, model)
    
    def handle_error(self, error: Exception, model: str) -> None:
        """Handle Google-specific errors."""
        error_msg = str(error).lower()
        
        # Google specific rate limit errors
        if any(term in error_msg for term in ['quota exceeded', 'rate limit', 'resource exhausted']):
            raise RateLimitError(f"Google rate limit exceeded for {model}: {error}")
        
        # Google API errors
        if any(term in error_msg for term in ['invalid argument', 'permission denied', 'unauthenticated']):
            raise APIError(f"Google API error for {model}: {error}")
        
        # Safety filter errors
        if 'safety' in error_msg or 'blocked' in error_msg:
            raise APIError(f"Google safety filter triggered for {model}: {error}")
        
        # Fall back to base error handling
        super().handle_error(error, model)