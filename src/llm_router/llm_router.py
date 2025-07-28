"""Main LLM Router class with multi-provider fallback logic."""

import yaml
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .usage_tracker import UsageTracker
from .providers import (
    BaseProvider, LLMError, RateLimitError, APIError,
    OpenAIProvider, AnthropicProvider, GoogleProvider, 
    GroqProvider, OpenRouterProvider, OllamaProvider
)

logger = logging.getLogger(__name__)


class LLMRouter:
    """Multi-provider LLM request router with automatic fallback."""
    
    def __init__(self, config_path: str = "ai_config.yaml"):
        """
        Initialize LLM router with configuration.
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.usage_tracker = self._init_usage_tracker()
        self.providers = self._init_providers()
        
        # Circuit breaker state - track consecutive failures per provider
        self.provider_failures = {}
        self.max_consecutive_failures = 3
        
        logger.info(f"LLM Router initialized with {len(self.providers)} providers")
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.debug(f"Loaded config from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing config file: {e}")
            raise
    
    def _init_usage_tracker(self) -> UsageTracker:
        """Initialize usage tracker based on config."""
        rate_config = self.config.get('rate_limiting', {})
        
        if not rate_config.get('enabled', True):
            logger.warning("Rate limiting disabled")
            return None
        
        storage_backend = rate_config.get('storage_backend', 'json')
        storage_path = rate_config.get('storage_path', 'usage_counters.json')
        
        return UsageTracker(storage_backend, storage_path)
    
    def _init_providers(self) -> Dict[str, BaseProvider]:
        """Initialize all available providers."""
        provider_classes = {
            'openai': OpenAIProvider,
            'anthropic': AnthropicProvider,
            'google': GoogleProvider,
            'groq': GroqProvider,
            'openrouter': OpenRouterProvider,
            'ollama': OllamaProvider
        }
        
        providers = {}
        
        # Create a mapping of provider configs by name
        provider_configs = {}
        for provider_config in self.config.get('providers', []):
            provider_configs[provider_config['name']] = provider_config
        
        for provider_name, provider_class in provider_classes.items():
            try:
                # Pass provider config if available (for providers like Ollama that need it)
                provider_config = provider_configs.get(provider_name, {})
                if provider_name == 'ollama':
                    provider = provider_class(provider_config)
                else:
                    provider = provider_class()
                
                if provider.is_available():
                    providers[provider_name] = provider
                    logger.debug(f"Initialized {provider_name} provider")
                else:
                    logger.debug(f"Skipped {provider_name} provider (not available)")
            except Exception as e:
                logger.warning(f"Failed to initialize {provider_name} provider: {e}")
        
        return providers
    
    def _get_available_models(self) -> List[Dict]:
        """Get list of available models from config, filtering by provider availability."""
        available_models = []
        
        for provider_config in self.config.get('providers', []):
            provider_name = provider_config['name']
            
            # Skip if provider not available
            if provider_name not in self.providers:
                logger.debug(f"Skipping {provider_name} models (provider not available)")
                continue
            
            # Add models from this provider
            for model_config in provider_config.get('models', []):
                # Get default values from config or use built-in defaults
                default_rpm = self.config.get('defaults', {}).get('rpm', 10)
                default_rpd = self.config.get('defaults', {}).get('rpd', 1000)
                default_timeout = self.config.get('defaults', {}).get('timeout', 30)
                
                available_models.append({
                    'provider': provider_name,
                    'model': model_config['model'],
                    'rpm': model_config.get('rpm', default_rpm),
                    'rpd': model_config.get('rpd', default_rpd),
                    'timeout': model_config.get('timeout', default_timeout)
                })
        
        return available_models
    
    def _can_use_model(self, provider: str, model: str, rpm: int, rpd: int) -> bool:
        """Check if model can be used (rate limits)."""
        if not self.usage_tracker:
            return True  # No rate limiting
        
        return self.usage_tracker.can_make_request(provider, model, rpm, rpd)
    
    def _record_success(self, provider: str, model: str) -> None:
        """Record successful request."""
        if self.usage_tracker:
            self.usage_tracker.record_request(provider, model)
    
    def query(self, prompt: str, **kwargs) -> str:
        """
        Query LLM with automatic provider/model fallback.
        
        Args:
            prompt: Text prompt to send
            **kwargs: Additional parameters for the model
            
        Returns:
            str: Model response
            
        Raises:
            RuntimeError: When all providers/models fail or are rate-limited
        """
        available_models = self._get_available_models()
        
        if not available_models:
            raise RuntimeError("No LLM providers available")
        
        last_error = None
        attempts = []
        
        for model_config in available_models:
            provider_name = model_config['provider']
            model_name = model_config['model']
            rpm = model_config['rpm']
            rpd = model_config['rpd']
            
            provider = self.providers[provider_name]
            
            # Check circuit breaker
            provider_key = f"{provider_name}:{model_name}"
            if self.provider_failures.get(provider_key, 0) >= self.max_consecutive_failures:
                logger.debug(f"Skipping {provider_name}:{model_name} (circuit breaker open)")
                attempts.append(f"{provider_name}:{model_name} (circuit breaker)")
                continue
            
            # Check rate limits
            if not self._can_use_model(provider_name, model_name, rpm, rpd):
                logger.debug(f"Skipping {provider_name}:{model_name} (rate limited)")
                attempts.append(f"{provider_name}:{model_name} (rate limited)")
                continue
            
            # Validate model with provider
            if not provider.validate_model(model_name):
                logger.warning(f"Invalid model {model_name} for provider {provider_name}")
                attempts.append(f"{provider_name}:{model_name} (invalid model)")
                continue
            
            # Attempt query
            try:
                logger.info(f"Attempting query with {provider_name}:{model_name}")
                
                # Add timeout to kwargs
                query_kwargs = kwargs.copy()
                query_kwargs['timeout'] = model_config['timeout']
                
                response = provider.query_model(model_name, prompt, **query_kwargs)
                
                # Check for empty response
                if not response or not response.strip():
                    logger.warning(f"Empty response from {provider_name}:{model_name}")
                    attempts.append(f"{provider_name}:{model_name} (empty response)")
                    continue
                
                # Record success and reset circuit breaker
                self._record_success(provider_name, model_name)
                self.provider_failures[provider_key] = 0  # Reset failure count
                
                logger.info(f"Successfully queried {provider_name}:{model_name}")
                return response
                
            except RateLimitError as e:
                logger.warning(f"Rate limit hit for {provider_name}:{model_name}: {e}")
                attempts.append(f"{provider_name}:{model_name} (rate limit)")
                last_error = e
                # Add brief delay before trying next provider to avoid rapid exhaustion
                import time
                time.sleep(1)
                continue
                
            except APIError as e:
                logger.warning(f"API error for {provider_name}:{model_name}: {e}")
                attempts.append(f"{provider_name}:{model_name} (API error)")
                last_error = e
                # Increment failure count
                self.provider_failures[provider_key] = self.provider_failures.get(provider_key, 0) + 1
                continue
                
            except LLMError as e:
                logger.warning(f"LLM error for {provider_name}:{model_name}: {e}")
                attempts.append(f"{provider_name}:{model_name} (LLM error)")
                last_error = e
                # Increment failure count
                self.provider_failures[provider_key] = self.provider_failures.get(provider_key, 0) + 1
                continue
                
            except Exception as e:
                logger.error(f"Unexpected error for {provider_name}:{model_name}: {e}")
                attempts.append(f"{provider_name}:{model_name} (unexpected error)")
                last_error = e
                # Increment failure count
                self.provider_failures[provider_key] = self.provider_failures.get(provider_key, 0) + 1
                continue
        
        # All models failed
        error_msg = f"All LLM providers failed or are rate-limited. Attempts: {', '.join(attempts)}"
        if last_error:
            error_msg += f". Last error: {last_error}"
        
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    def get_usage_stats(self) -> List[Dict]:
        """Get usage statistics for all models."""
        if not self.usage_tracker:
            return []
        
        return self.usage_tracker.get_all_usage_stats()
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return list(self.providers.keys())
    
    def get_provider_models(self, provider_name: str) -> List[str]:
        """Get list of models for a specific provider."""
        models = []
        for provider_config in self.config.get('providers', []):
            if provider_config['name'] == provider_name:
                models = [m['model'] for m in provider_config.get('models', [])]
                break
        return models
    
    def reload_config(self) -> None:
        """Reload configuration from file."""
        self.config = self._load_config()
        logger.info("Configuration reloaded")
    
    def test_providers(self) -> Dict[str, Dict]:
        """Test all providers with a simple query."""
        test_prompt = "Hello, please respond with just 'OK' to confirm you're working."
        results = {}
        
        for provider_name in self.providers.keys():
            results[provider_name] = {}
            
            # Get models for this provider
            models = self.get_provider_models(provider_name)
            
            for model in models:
                try:
                    # Skip rate limited models
                    model_config = None
                    for p in self.config.get('providers', []):
                        if p['name'] == provider_name:
                            for m in p.get('models', []):
                                if m['model'] == model:
                                    model_config = m
                                    break
                            break
                    
                    if model_config and not self._can_use_model(
                        provider_name, model, 
                        model_config.get('rpm', 10), 
                        model_config.get('rpd', 1000)
                    ):
                        results[provider_name][model] = "RATE_LIMITED"
                        continue
                    
                    # Test the model
                    provider = self.providers[provider_name]
                    response = provider.query_model(model, test_prompt, max_tokens=10)
                    results[provider_name][model] = "OK" if response else "EMPTY_RESPONSE"
                    
                except Exception as e:
                    results[provider_name][model] = f"ERROR: {str(e)[:100]}"
        
        return results
    
    def generate_batch_summaries(self, articles: List[Dict]) -> 'AIResponse':
        """Generate summaries for multiple articles in a single API call.
        
        This method provides compatibility with the enhanced_ai_processor that expects
        batch summary generation from the AIServiceManager interface.
        """
        # Import AIResponse for compatibility
        try:
            from ..ai_adapters import AIResponse
        except ImportError:
            try:
                from src.ai_adapters import AIResponse
            except ImportError:
                from ai_adapters import AIResponse
        
        try:
            # Build a batch prompt for multiple article summaries
            batch_prompt = f"""You are a professional news summarizer. Create concise summaries for each article below.

**BATCH SUMMARIZATION GUIDELINES:**
1. Create exactly 2-3 sentences per article
2. Maintain consistent style and tone across all summaries
3. Include main points, findings, or events for each article
4. Use factual, neutral language
5. Return results as a valid JSON array of strings

**ARTICLES TO SUMMARIZE:**
"""
            
            for i, article in enumerate(articles, 1):
                title = article.get('title', 'Untitled')
                content = article.get('original_summary', '') or article.get('content', '')
                batch_prompt += f"""
**Article {i}:**
Title: {title}
Content: {content[:500]}
"""
            
            batch_prompt += f"""
**REQUIRED OUTPUT FORMAT:**
[
  "Summary for article 1 (2-3sentences).",
  "Summary for article 2 (2-3 sentences).",
  ...
]

Return ONLY the JSON array with {len(articles)} summary strings, no other text."""
            
            # Use the LLMRouter query method
            response_text = self.query(batch_prompt, max_tokens=1000)
            
            # Try to parse as JSON
            import json
            try:
                summaries = json.loads(response_text)
                if isinstance(summaries, list):
                    return AIResponse(json.dumps(summaries), True, "llm_router", "llm_router", 0, 0.01)
                else:
                    raise ValueError("Response is not a list")
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, create individual summaries
                logger.warning("Batch response not valid JSON, falling back to individual summaries")
                summaries = []
                for article in articles:
                    try:
                        title = article.get('title', 'Untitled')
                        content = article.get('original_summary', '') or article.get('content', '')
                        individual_prompt = f"""Create a concise news summary in exactly 2-3 sentences:

Title: {title}
Content: {content[:300]}

Focus on the main facts and provide only the summary text:"""
                        summary = self.query(individual_prompt, max_tokens=150)
                        summaries.append(summary)
                    except Exception as e:
                        logger.error(f"Failed to generate individual summary: {e}")
                        summaries.append(f"Summary unavailable for: {title}")
                
                return AIResponse(json.dumps(summaries), True, "llm_router", "llm_router", 0, 0.02)
                
        except Exception as e:
            logger.error(f"Batch summary generation failed: {e}")
            return AIResponse(f"Batch summary generation failed: {e}", False, "llm_router", "llm_router", 0, 0.0)
    
    def classify_article(self, title: str, content: str) -> 'AIResponse':
        """Classify an article into categories.
        
        Provides compatibility with enhanced_ai_processor classification interface.
        """
        try:
            from ..ai_adapters import AIResponse
        except ImportError:
            try:
                from src.ai_adapters import AIResponse
            except ImportError:
                from ai_adapters import AIResponse
        
        try:
            # Classification prompt
            categories = [
                "Science & Discovery", "Technology & Gadgets", "Health & Wellness", 
                "Business & Finance", "Global Affairs", "Environment & Climate",
                "Good Vibes (Positive News)", "Pop Culture & Lifestyle", 
                "For Young Minds (Youth-Focused)", "DIY, Skills & How-To"
            ]
            
            prompt = f"""You are a news article classifier. Analyze the article below and classify it into the most relevant categories.

**AVAILABLE CATEGORIES:**
{chr(10).join(f"- {cat}" for cat in categories)}

**CLASSIFICATION RULES:**
1. Select 1-3 most relevant categories (avoid over-classification)
2. Focus on the main topic/theme of the article
3. Use exact category names from the list above
4. Return ONLY a valid JSON array format

**ARTICLE TO CLASSIFY:**
Title: {title}
Content: {content[:800]}

**REQUIRED OUTPUT FORMAT:**
["Category Name 1", "Category Name 2"]

Return only the JSON array, no other text or explanation."""
            
            response_text = self.query(prompt, max_tokens=200)
            
            # Try to parse as JSON
            import json
            try:
                classified_categories = json.loads(response_text)
                if isinstance(classified_categories, list):
                    return AIResponse(json.dumps(classified_categories), True, "llm_router", "llm_router", 0, 0.005)
                else:
                    raise ValueError("Response is not a list")
            except (json.JSONDecodeError, ValueError):
                logger.warning("Classification response not valid JSON, using fallback")
                # Fallback classification
                fallback_categories = ["Technology & Gadgets"]  # Default category
                return AIResponse(json.dumps(fallback_categories), True, "llm_router", "llm_router", 0, 0.005)
                
        except Exception as e:
            logger.error(f"Article classification failed: {e}")
            return AIResponse(f"Classification failed: {e}", False, "llm_router", "llm_router", 0, 0.0)
    
    def generate_summary(self, title: str, content: str) -> 'AIResponse':
        """Generate a summary for an article.
        
        Provides compatibility with enhanced_ai_processor summary interface.
        """
        try:
            from ..ai_adapters import AIResponse
        except ImportError:
            try:
                from src.ai_adapters import AIResponse
            except ImportError:
                from ai_adapters import AIResponse
        
        try:
            prompt = f"""You are a professional news summarizer. Create a concise, informative summary of the article below.

**SUMMARIZATION GUIDELINES:**
1. Write exactly 2-3 clear, complete sentences
2. Include the main point/finding/event from the article
3. Maintain factual accuracy and neutral tone
4. Focus on WHO, WHAT, WHEN, WHERE, WHY (as applicable)
5. Use active voice when possible

**ARTICLE TO SUMMARIZE:**
Title: {title}
Content: {content[:800]}

**REQUIRED OUTPUT:**
Provide only the summary text (2-3 sentences), no other formatting or text."""
            
            summary = self.query(prompt, max_tokens=200)
            return AIResponse(summary.strip(), True, "llm_router", "llm_router", 0, 0.005)
            
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return AIResponse(f"Summary generation failed: {e}", False, "llm_router", "llm_router", 0, 0.0)
    
    def detect_trends(self, articles: List[Dict]) -> 'AIResponse':
        """Detect trends from a list of articles.
        
        Provides compatibility with enhanced_ai_processor trend detection interface.
        """
        try:
            from ..ai_adapters import AIResponse
        except ImportError:
            try:
                from src.ai_adapters import AIResponse
            except ImportError:
                from ai_adapters import AIResponse
        
        try:
            # Build trend detection prompt
            prompt = "Analyze these article titles and identify trending topics. Return a JSON array of trending topic strings:\n\n"
            
            for i, article in enumerate(articles[:20], 1):  # Limit to 20 articles
                title = article.get('title', 'Untitled')
                prompt += f"{i}. {title}\n"
            
            prompt += "\nReturn only a JSON array of trending topic strings, nothing else."
            
            response_text = self.query(prompt, max_tokens=300)
            
            # Try to parse as JSON
            import json
            try:
                trends = json.loads(response_text)
                if isinstance(trends, list):
                    return AIResponse(json.dumps(trends), True, "llm_router", "llm_router", 0, 0.01)
                else:
                    raise ValueError("Response is not a list")
            except (json.JSONDecodeError, ValueError):
                logger.warning("Trend detection response not valid JSON, using fallback")
                return AIResponse(json.dumps(["Technology Updates", "Current Events"]), True, "llm_router", "llm_router", 0, 0.01)
                
        except Exception as e:
            logger.error(f"Trend detection failed: {e}")
            return AIResponse(f"Trend detection failed: {e}", False, "llm_router", "llm_router", 0, 0.0)
    
    def get_usage_stats(self) -> Dict[str, Dict]:
        """Get usage statistics.
        
        Provides compatibility with enhanced_ai_processor stats interface.
        """
        # Return basic stats from usage tracker if available
        if self.usage_tracker:
            return {"llm_router": self.usage_tracker.get_all_usage_stats()}
        else:
            return {"llm_router": {"requests_made": 0, "requests_failed": 0}}
    
    def get_available_adapters(self) -> List[str]:
        """Get list of available adapters/providers.
        
        Provides compatibility with enhanced_ai_processor adapter listing.
        """
        return list(self.providers.keys())