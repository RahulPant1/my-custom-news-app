"""OpenRouter provider adapter."""

import os
import requests
from typing import Dict, Any
import logging
from .base import BaseProvider, RateLimitError, APIError, LLMError

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseProvider):
    """OpenRouter API provider adapter."""
    
    def __init__(self, api_key: str = None):
        """Initialize OpenRouter provider."""
        super().__init__(api_key or os.getenv('OPENROUTER_API_KEY'))
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
    
    def is_available(self) -> bool:
        """Check if OpenRouter is available."""
        return self.api_key is not None
    
    def validate_model(self, model: str) -> bool:
        """Validate OpenRouter model."""
        # OpenRouter supports many models, we'll allow any string
        # In practice, you might want to validate against their model list
        return len(model) > 0
    
    def get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for OpenRouter."""
        return {
            'temperature': 0.7,
            'max_tokens': 1000,
            'top_p': 1.0
        }
    
    def query_model(self, model: str, prompt: str, **kwargs) -> str:
        """Query OpenRouter model."""
        if not self.is_available():
            raise LLMError("OpenRouter provider not available")
        
        if not self.validate_model(model):
            raise LLMError(f"Invalid OpenRouter model: {model}")
        
        # Merge parameters
        params = self.get_default_params()
        params.update(kwargs)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-username/llm-router",  # Optional
            "X-Title": "LLM Router"  # Optional
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": params.get('temperature', 0.7),
            "max_tokens": params.get('max_tokens', 1000),
            "top_p": params.get('top_p', 1.0)
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=params.get('timeout', 60)
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                raise APIError(f"OpenRouter API returned status {response.status_code}: {response.text}")
            
        except requests.RequestException as e:
            self.handle_error(e, model)
        except KeyError as e:
            raise APIError(f"Unexpected response format from OpenRouter: {e}")
    
    def handle_error(self, error: Exception, model: str) -> None:
        """Handle OpenRouter-specific errors."""
        if isinstance(error, requests.RequestException):
            if hasattr(error, 'response') and error.response is not None:
                status_code = error.response.status_code
                
                if status_code == 429:
                    raise RateLimitError(f"OpenRouter rate limit exceeded for {model}: {error}")
                elif status_code in [401, 403]:
                    raise APIError(f"OpenRouter authentication error for {model}: {error}")
                elif status_code >= 500:
                    raise APIError(f"OpenRouter server error for {model}: {error}")
        
        # Fall back to base error handling
        super().handle_error(error, model)