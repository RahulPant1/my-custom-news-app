"""Ollama provider for local model inference."""

import requests
import logging
from typing import Dict, Any

from .base import BaseProvider, LLMError

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """Provider for Ollama local models."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Ollama provider.
        
        Args:
            config: Provider configuration including host and port
        """
        super().__init__(None)  # No API key needed for local models
        config = config or {}
        self.host = config.get('host', 'http://localhost:11434')
        self.timeout = config.get('timeout', 60)  # Longer timeout for local models
    
    def is_available(self) -> bool:
        """Check if Ollama is available and running."""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def query_model(self, model: str, prompt: str, **kwargs) -> str:
        """
        Query the specified model with a prompt.
        
        Args:
            model: Model identifier (e.g., 'llama3.2:3b-instruct-q8_0')
            prompt: Text prompt to send
            **kwargs: Additional parameters
            
        Returns:
            str: Model response text
            
        Raises:
            LLMError: If generation fails
        """
        return self.generate(prompt, model, **kwargs)
    
    def generate(self, prompt: str, model: str, **kwargs) -> str:
        """
        Generate response using Ollama.
        
        Args:
            prompt: Input prompt
            model: Model name (e.g., 'llama3.2:3b-instruct-q8_0')
            **kwargs: Additional parameters
            
        Returns:
            str: Generated response
            
        Raises:
            LLMError: If generation fails
        """
        try:
            # Prepare request payload
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,  # Get complete response
                "options": {
                    "temperature": kwargs.get('temperature', 0.7),
                    "top_p": kwargs.get('top_p', 0.9),
                    "max_tokens": kwargs.get('max_tokens', 2048),
                }
            }
            
            # Add any custom options
            if 'options' in kwargs:
                payload['options'].update(kwargs['options'])
            
            logger.debug(f"Ollama request to {self.host}/api/generate with model {model}")
            
            # Make request to Ollama
            response = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if 'response' not in result:
                raise LLMError(f"Unexpected Ollama response format: {result}")
            
            generated_text = result['response'].strip()
            
            logger.debug(f"Ollama generation successful, response length: {len(generated_text)}")
            return generated_text
            
        except requests.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            raise LLMError(f"Ollama request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise LLMError(f"Ollama generation error: {str(e)}")
    
    def get_models(self) -> list:
        """Get list of available models from Ollama."""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model in data.get('models', []):
                models.append({
                    'name': model.get('name', ''),
                    'size': model.get('size', 0),
                    'modified_at': model.get('modified_at', ''),
                    'digest': model.get('digest', '')
                })
            
            return models
            
        except requests.RequestException as e:
            logger.warning(f"Failed to get Ollama models: {e}")
            return []
    
    def check_model_available(self, model: str) -> bool:
        """Check if a specific model is available in Ollama."""
        models = self.get_models()
        available_names = [m['name'] for m in models]
        return model in available_names