"""Multi-API adapter system for AI services."""

import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# AI service imports
try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from config import AI_CATEGORIES
except ImportError:
    AI_CATEGORIES = ['Science & Discovery', 'Technology & Gadgets', 'Health & Wellness', 'Business & Finance', 'Global Affairs', 'Environment & Climate', 'Good Vibes (Positive News)', 'Pop Culture & Lifestyle', 'For Young Minds (Youth-Focused)', 'DIY, Skills & How-To']

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """Standardized response from AI services."""
    content: str
    success: bool
    provider: str
    model: str
    tokens_used: int = 0
    cost_estimate: float = 0.0
    error: Optional[str] = None


class AIAdapter(ABC):
    """Abstract base class for AI service adapters."""
    
    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model
        self.provider_name = self.__class__.__name__.replace('Adapter', '')
        self.last_request_time = 0
        self.rate_limit_delay = 1.0  # Minimum seconds between requests
    
    def _rate_limit(self):
        """Apply rate limiting between API calls."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    @abstractmethod
    def classify_article(self, title: str, summary: str) -> AIResponse:
        """Classify an article into categories."""
        pass
    
    @abstractmethod
    def generate_summary(self, title: str, content: str) -> AIResponse:
        """Generate a summary of an article."""
        pass
    
    @abstractmethod
    def detect_trends(self, articles: List[Dict]) -> AIResponse:
        """Detect trending topics from articles."""
        pass
    
    @abstractmethod
    def generate_batch_summaries(self, articles: List[Dict]) -> AIResponse:
        """Generate summaries for multiple articles in a single API call."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the AI service is available."""
        pass


class OpenAIAdapter(AIAdapter):
    """OpenAI API adapter."""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        super().__init__(api_key, model)
        if not openai:
            raise ImportError("OpenAI library not installed. Run: pip install openai")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.rate_limit_delay = 1.0
    
    def is_available(self) -> bool:
        """Check if OpenAI service is available."""
        try:
            # Test with a minimal request
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            logger.warning(f"OpenAI not available: {e}")
            return False
    
    def classify_article(self, title: str, summary: str) -> AIResponse:
        """Classify article using OpenAI."""
        self._rate_limit()
        
        prompt = f"""
        Classify this news article into one or more of the following categories. Return only the category names as a JSON list.
        
        Categories:
        {json.dumps(AI_CATEGORIES, indent=2)}
        
        Article Title: {title}
        Article Summary: {summary[:500]}
        
        Instructions:
        - Select 1-3 most relevant categories
        - Return as JSON array of category names exactly as listed above
        - Focus on the primary topics and themes
        
        Response format: ["Category Name 1", "Category Name 2"]
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert news classifier. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # Parse and validate response
            try:
                categories = json.loads(content)
                valid_categories = [cat for cat in categories if cat in AI_CATEGORIES]
                final_categories = valid_categories if valid_categories else [AI_CATEGORIES[0]]
                
                return AIResponse(
                    content=json.dumps(final_categories),
                    success=True,
                    provider="OpenAI",
                    model=self.model,
                    tokens_used=tokens_used,
                    cost_estimate=self._estimate_cost(tokens_used)
                )
            except json.JSONDecodeError:
                # Fallback parsing
                found_categories = []
                for category in AI_CATEGORIES:
                    if category.lower() in content.lower():
                        found_categories.append(category)
                
                result_categories = found_categories if found_categories else [AI_CATEGORIES[0]]
                
                return AIResponse(
                    content=json.dumps(result_categories),
                    success=True,
                    provider="OpenAI",
                    model=self.model,
                    tokens_used=tokens_used,
                    cost_estimate=self._estimate_cost(tokens_used)
                )
        
        except Exception as e:
            logger.error(f"OpenAI classification error: {e}")
            return AIResponse(
                content=json.dumps([AI_CATEGORIES[0]]),
                success=False,
                provider="OpenAI",
                model=self.model,
                error=str(e)
            )
    
    def generate_summary(self, title: str, content: str) -> AIResponse:
        """Generate summary using OpenAI."""
        self._rate_limit()
        
        prompt = f"""
        Create a concise, engaging summary of this news article. The summary should be informative and suitable for a news digest.
        
        Article Title: {title}
        Original Content: {content[:800]}
        
        Requirements:
        - 2-3 sentences maximum
        - Clear and engaging language
        - Focus on key facts and implications
        - Suitable for general audience
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert news writer. Create clear, concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.4
            )
            
            summary = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # Clean up summary
            summary = summary.strip('"\'')
            
            return AIResponse(
                content=summary,
                success=True,
                provider="OpenAI",
                model=self.model,
                tokens_used=tokens_used,
                cost_estimate=self._estimate_cost(tokens_used)
            )
        
        except Exception as e:
            logger.error(f"OpenAI summary error: {e}")
            fallback_summary = content[:200] + "..." if len(content) > 200 else content
            
            return AIResponse(
                content=fallback_summary,
                success=False,
                provider="OpenAI",
                model=self.model,
                error=str(e)
            )
    
    def detect_trends(self, articles: List[Dict]) -> AIResponse:
        """Detect trends using OpenAI."""
        self._rate_limit()
        
        if len(articles) < 3:
            return AIResponse(
                content="{}",
                success=True,
                provider="OpenAI",
                model=self.model
            )
        
        # Prepare article summaries
        article_texts = []
        for article in articles[:15]:  # Limit for token efficiency
            text = f"Title: {article['title']}\nSummary: {article.get('original_summary', '')[:150]}"
            article_texts.append(text)
        
        combined_text = "\n\n---\n\n".join(article_texts)
        
        prompt = f"""
        Analyze these news articles and identify trending topics that appear across multiple articles.
        
        Articles:
        {combined_text}
        
        Return trending topics as JSON object with categories as keys and topic arrays as values:
        {{
            "Technology & Gadgets": ["AI developments", "New product launches"],
            "Science & Discovery": ["Research breakthroughs"]
        }}
        
        Only include topics mentioned in 3+ articles. If no clear trends, return empty object {{}}.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a news trend analyst. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            try:
                trends = json.loads(content)
                return AIResponse(
                    content=json.dumps(trends) if isinstance(trends, dict) else "{}",
                    success=True,
                    provider="OpenAI",
                    model=self.model,
                    tokens_used=tokens_used,
                    cost_estimate=self._estimate_cost(tokens_used)
                )
            except json.JSONDecodeError:
                return AIResponse(
                    content="{}",
                    success=False,
                    provider="OpenAI",
                    model=self.model,
                    error="Invalid JSON response"
                )
        
        except Exception as e:
            logger.error(f"OpenAI trend detection error: {e}")
            return AIResponse(
                content="{}",
                success=False,
                provider="OpenAI",
                model=self.model,
                error=str(e)
            )
    
    def generate_batch_summaries(self, articles: List[Dict]) -> AIResponse:
        """Generate batch summaries using OpenAI."""
        self._rate_limit()
        
        if not articles:
            return AIResponse(content="[]", success=True, provider="OpenAI", model=self.model)
        
        # Prepare articles for batch processing
        article_texts = []
        for i, article in enumerate(articles[:8]):  # Limit to 8 articles for OpenAI
            title = article.get('title', 'No title')
            content = article.get('original_summary', article.get('content', ''))[:500]
            article_texts.append(f"Article {i+1}:\nTitle: {title}\nContent: {content}")
        
        prompt = f"""Summarize each of these news articles in 2-3 clear sentences. Return your response as a JSON array where each element is a summary for the corresponding article.

{chr(10).join(article_texts)}

Return format: ["Summary 1", "Summary 2", "Summary 3", ...]

Requirements:
- Each summary should be 2-3 sentences
- Maintain the same order as the input articles
- Return valid JSON array format
- Make summaries engaging and informative"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert news summarizer. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            try:
                summaries = json.loads(content)
                if isinstance(summaries, list) and len(summaries) <= len(articles):
                    return AIResponse(
                        content=json.dumps(summaries),
                        success=True,
                        provider="OpenAI",
                        model=self.model,
                        tokens_used=tokens_used,
                        cost_estimate=self._estimate_cost(tokens_used)
                    )
            except json.JSONDecodeError:
                logger.warning("Failed to parse OpenAI batch summaries as JSON")
            
            # Fallback: return individual fallback summaries
            fallback_summaries = [
                article.get('original_summary', article.get('title', 'No summary'))[:200] + "..."
                for article in articles
            ]
            return AIResponse(
                content=json.dumps(fallback_summaries),
                success=False,
                provider="OpenAI",
                model=self.model,
                tokens_used=tokens_used,
                error="JSON parsing failed"
            )
        
        except Exception as e:
            logger.error(f"OpenAI batch summary error: {e}")
            fallback_summaries = [
                article.get('original_summary', article.get('title', 'No summary'))[:200] + "..."
                for article in articles
            ]
            return AIResponse(
                content=json.dumps(fallback_summaries),
                success=False,
                provider="OpenAI",
                model=self.model,
                error=str(e)
            )
    
    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost based on token usage (rough approximation)."""
        if self.model.startswith("gpt-4"):
            return tokens * 0.00003  # $0.03 per 1K tokens (rough average)
        else:
            return tokens * 0.000002  # $0.002 per 1K tokens for GPT-3.5


class AnthropicAdapter(AIAdapter):
    """Anthropic Claude API adapter."""
    
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        super().__init__(api_key, model)
        if not anthropic:
            raise ImportError("Anthropic library not installed. Run: pip install anthropic")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.rate_limit_delay = 1.5
    
    def is_available(self) -> bool:
        """Check if Anthropic service is available."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception as e:
            logger.warning(f"Anthropic not available: {e}")
            return False
    
    def classify_article(self, title: str, summary: str) -> AIResponse:
        """Classify article using Claude."""
        self._rate_limit()
        
        prompt = f"""Classify this news article into 1-3 categories from this list:
        
        {', '.join(AI_CATEGORIES)}
        
        Article: "{title}"
        Summary: {summary[:500]}
        
        Respond with only a JSON array of category names: ["Category 1", "Category 2"]"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            
            try:
                categories = json.loads(content)
                valid_categories = [cat for cat in categories if cat in AI_CATEGORIES]
                final_categories = valid_categories if valid_categories else [AI_CATEGORIES[0]]
                
                return AIResponse(
                    content=json.dumps(final_categories),
                    success=True,
                    provider="Anthropic",
                    model=self.model,
                    tokens_used=tokens_used,
                    cost_estimate=self._estimate_cost(tokens_used)
                )
            except json.JSONDecodeError:
                # Fallback parsing
                found_categories = []
                for category in AI_CATEGORIES:
                    if category.lower() in content.lower():
                        found_categories.append(category)
                
                result_categories = found_categories if found_categories else [AI_CATEGORIES[0]]
                return AIResponse(
                    content=json.dumps(result_categories),
                    success=True,
                    provider="Anthropic",
                    model=self.model,
                    tokens_used=tokens_used
                )
        
        except Exception as e:
            logger.error(f"Anthropic classification error: {e}")
            return AIResponse(
                content=json.dumps([AI_CATEGORIES[0]]),
                success=False,
                provider="Anthropic",
                model=self.model,
                error=str(e)
            )
    
    def generate_summary(self, title: str, content: str) -> AIResponse:
        """Generate summary using Claude."""
        self._rate_limit()
        
        prompt = f"""Create a 2-3 sentence summary of this article for a news digest:
        
        Title: {title}
        Content: {content[:800]}
        
        Make it clear, engaging, and informative."""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}]
            )
            
            summary = response.content[0].text.strip()
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            
            return AIResponse(
                content=summary,
                success=True,
                provider="Anthropic",
                model=self.model,
                tokens_used=tokens_used,
                cost_estimate=self._estimate_cost(tokens_used)
            )
        
        except Exception as e:
            logger.error(f"Anthropic summary error: {e}")
            return AIResponse(
                content=content[:200] + "..." if len(content) > 200 else content,
                success=False,
                provider="Anthropic",
                model=self.model,
                error=str(e)
            )
    
    def detect_trends(self, articles: List[Dict]) -> AIResponse:
        """Detect trends using Claude."""
        self._rate_limit()
        
        if len(articles) < 3:
            return AIResponse(content="{}", success=True, provider="Anthropic", model=self.model)
        
        article_texts = []
        for article in articles[:15]:
            text = f"{article['title']}: {article.get('original_summary', '')[:100]}"
            article_texts.append(text)
        
        prompt = f"""Find trending topics in these articles. Return JSON format:
        
        {chr(10).join(article_texts)}
        
        Return: {{"Category": ["trend1", "trend2"]}} or {{}} if no trends found."""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            
            try:
                trends = json.loads(content)
                return AIResponse(
                    content=json.dumps(trends) if isinstance(trends, dict) else "{}",
                    success=True,
                    provider="Anthropic",
                    model=self.model,
                    tokens_used=tokens_used,
                    cost_estimate=self._estimate_cost(tokens_used)
                )
            except json.JSONDecodeError:
                return AIResponse(
                    content="{}",
                    success=False,
                    provider="Anthropic",
                    model=self.model,
                    error="Invalid JSON response"
                )
        
        except Exception as e:
            logger.error(f"Anthropic trend detection error: {e}")
            return AIResponse(
                content="{}",
                success=False,
                provider="Anthropic",
                model=self.model,
                error=str(e)
            )
    
    def generate_batch_summaries(self, articles: List[Dict]) -> AIResponse:
        """Generate batch summaries using Claude."""
        self._rate_limit()
        
        if not articles:
            return AIResponse(content="[]", success=True, provider="Anthropic", model=self.model)
        
        # Prepare articles for batch processing
        article_texts = []
        for i, article in enumerate(articles[:6]):  # Limit to 6 articles for Anthropic
            title = article.get('title', 'No title')
            content = article.get('original_summary', article.get('content', ''))[:400]
            article_texts.append(f"Article {i+1}:\nTitle: {title}\nContent: {content}")
        
        prompt = f"""Summarize each of these news articles in 2-3 clear sentences. Return your response as a JSON array where each element is a summary for the corresponding article.

{chr(10).join(article_texts)}

Return format: ["Summary 1", "Summary 2", "Summary 3", ...]

Requirements:
- Each summary should be 2-3 sentences
- Maintain the same order as the input articles
- Return valid JSON array format
- Make summaries engaging and informative"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            
            try:
                summaries = json.loads(content)
                if isinstance(summaries, list) and len(summaries) <= len(articles):
                    return AIResponse(
                        content=json.dumps(summaries),
                        success=True,
                        provider="Anthropic",
                        model=self.model,
                        tokens_used=tokens_used,
                        cost_estimate=self._estimate_cost(tokens_used)
                    )
            except json.JSONDecodeError:
                logger.warning("Failed to parse Anthropic batch summaries as JSON")
            
            # Fallback summaries
            fallback_summaries = [
                article.get('original_summary', article.get('title', 'No summary'))[:200] + "..."
                for article in articles
            ]
            return AIResponse(
                content=json.dumps(fallback_summaries),
                success=False,
                provider="Anthropic",
                model=self.model,
                tokens_used=tokens_used,
                error="JSON parsing failed"
            )
        
        except Exception as e:
            logger.error(f"Anthropic batch summary error: {e}")
            fallback_summaries = [
                article.get('original_summary', article.get('title', 'No summary'))[:200] + "..."
                for article in articles
            ]
            return AIResponse(
                content=json.dumps(fallback_summaries),
                success=False,
                provider="Anthropic",
                model=self.model,
                error=str(e)
            )
    
    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost for Claude."""
        return tokens * 0.000008  # Rough estimate


class GoogleAIAdapter(AIAdapter):
    """Google AI (Gemini) adapter."""
    
    def __init__(self, api_key: str, model: str = None):
        # Use config default if no model specified
        if not model:
            from config import AI_MODELS
            model = AI_MODELS['google']['default']
        
        super().__init__(api_key, model)
        if not genai:
            raise ImportError("Google AI library not installed. Run: pip install google-generativeai")
        
        genai.configure(api_key=api_key)
        self.model_instance = genai.GenerativeModel(model)
        self.rate_limit_delay = 2.0
        self._availability_cache = None
        self._availability_cache_time = 0
    
    def is_available(self) -> bool:
        """Check if Google AI service is available (cached for 60 seconds)."""
        current_time = time.time()
        
        # Return cached result if available and not expired
        if (self._availability_cache is not None and 
            current_time - self._availability_cache_time < 60):
            return self._availability_cache
        
        try:
            # Make a minimal API call to test availability
            self._rate_limit()
            response = self.model_instance.generate_content("test")
            self._availability_cache = True
            self._availability_cache_time = current_time
            return True
        except Exception as e:
            logger.warning(f"Google AI not available: {e}")
            self._availability_cache = False
            self._availability_cache_time = current_time
            return False
    
    def classify_article(self, title: str, summary: str) -> AIResponse:
        """Classify article using Gemini."""
        self._rate_limit()
        
        prompt = f"""Classify this news article into categories. Choose 1-3 from: {', '.join(AI_CATEGORIES)}
        
        Article: {title}
        Summary: {summary[:500]}
        
        Return JSON array: ["Category 1", "Category 2"]"""
        
        try:
            response = self.model_instance.generate_content(prompt)
            content = response.text.strip()
            
            try:
                categories = json.loads(content)
                valid_categories = [cat for cat in categories if cat in AI_CATEGORIES]
                final_categories = valid_categories if valid_categories else [AI_CATEGORIES[0]]
                
                return AIResponse(
                    content=json.dumps(final_categories),
                    success=True,
                    provider="GoogleAI",
                    model=self.model
                )
            except json.JSONDecodeError:
                # Fallback
                found_categories = []
                for category in AI_CATEGORIES:
                    if category.lower() in content.lower():
                        found_categories.append(category)
                
                return AIResponse(
                    content=json.dumps(found_categories if found_categories else [AI_CATEGORIES[0]]),
                    success=True,
                    provider="GoogleAI",
                    model=self.model
                )
        
        except Exception as e:
            logger.error(f"Google AI classification error: {e}")
            return AIResponse(
                content=json.dumps([AI_CATEGORIES[0]]),
                success=False,
                provider="GoogleAI",
                model=self.model,
                error=str(e)
            )
    
    def generate_summary(self, title: str, content: str) -> AIResponse:
        """Generate summary using Gemini."""
        self._rate_limit()
        
        prompt = f"""Summarize this article in 2-3 clear sentences:
        
        {title}
        
        {content[:800]}"""
        
        try:
            response = self.model_instance.generate_content(prompt)
            summary = response.text.strip()
            
            return AIResponse(
                content=summary,
                success=True,
                provider="GoogleAI",
                model=self.model
            )
        
        except Exception as e:
            logger.error(f"Google AI summary error: {e}")
            return AIResponse(
                content=content[:200] + "..." if len(content) > 200 else content,
                success=False,
                provider="GoogleAI",
                model=self.model,
                error=str(e)
            )
    
    def detect_trends(self, articles: List[Dict]) -> AIResponse:
        """Detect trends using Gemini."""
        self._rate_limit()
        
        if len(articles) < 3:
            return AIResponse(content="{}", success=True, provider="GoogleAI", model=self.model)
        
        article_list = []
        for article in articles[:10]:
            article_list.append(f"• {article['title']}")
        
        prompt = f"""Find common topics in these articles:
        
        {chr(10).join(article_list)}
        
        Return JSON with trending topics: {{"Category": ["topic1"]}} or {{}}"""
        
        try:
            response = self.model_instance.generate_content(prompt)
            content = response.text.strip()
            
            try:
                trends = json.loads(content)
                return AIResponse(
                    content=json.dumps(trends) if isinstance(trends, dict) else "{}",
                    success=True,
                    provider="GoogleAI",
                    model=self.model
                )
            except json.JSONDecodeError:
                return AIResponse(
                    content="{}",
                    success=False,
                    provider="GoogleAI",
                    model=self.model,
                    error="Invalid JSON"
                )
        
        except Exception as e:
            return AIResponse(
                content="{}",
                success=False,
                provider="GoogleAI",
                model=self.model,
                error=str(e)
            )
    
    def generate_batch_summaries(self, articles: List[Dict]) -> AIResponse:
        """Generate summaries for multiple articles in a single API call."""
        self._rate_limit()
        
        if not articles:
            return AIResponse(
                content="[]",
                success=True,
                provider="GoogleAI",
                model=self.model
            )
        
        # Prepare articles for batch processing
        article_texts = []
        for i, article in enumerate(articles[:10]):  # Limit to 10 articles per batch
            title = article.get('title', 'No title')
            content = article.get('original_summary', article.get('content', ''))[:600]  # Limit content length
            article_texts.append(f"Article {i+1}:\nTitle: {title}\nContent: {content}")
        
        prompt = f"""Summarize each of these news articles in 2-3 clear sentences. Return your response as a JSON array where each element is a summary for the corresponding article.

{chr(10).join(article_texts)}

Return format: ["Summary 1", "Summary 2", "Summary 3", ...]

Important:
- Each summary should be 2-3 sentences
- Maintain the same order as the input articles
- Return valid JSON array format
- Make summaries engaging and informative"""
        
        try:
            response = self.model_instance.generate_content(prompt)
            content = response.text.strip()
            
            # Try to parse as JSON
            try:
                summaries = json.loads(content)
                if isinstance(summaries, list) and len(summaries) <= len(articles):
                    return AIResponse(
                        content=json.dumps(summaries),
                        success=True,
                        provider="GoogleAI",
                        model=self.model
                    )
                else:
                    logger.warning(f"Invalid batch summary format: expected list of {len(articles)} summaries")
            except json.JSONDecodeError:
                logger.warning("Failed to parse batch summaries as JSON, falling back to individual processing")
            
            # Fallback: try to extract summaries from text response
            fallback_summaries = self._extract_summaries_from_text(content, len(articles))
            return AIResponse(
                content=json.dumps(fallback_summaries),
                success=True,
                provider="GoogleAI",
                model=self.model
            )
        
        except Exception as e:
            logger.error(f"Google AI batch summary error: {e}")
            # Return fallback summaries
            fallback_summaries = [
                article.get('original_summary', article.get('title', 'No summary available'))[:200] + "..."
                for article in articles
            ]
            return AIResponse(
                content=json.dumps(fallback_summaries),
                success=False,
                provider="GoogleAI",
                model=self.model,
                error=str(e)
            )
    
    def _extract_summaries_from_text(self, text: str, expected_count: int) -> List[str]:
        """Extract summaries from text response when JSON parsing fails."""
        import re
        
        # Try to find numbered summaries
        patterns = [
            r'(?:Summary )?(\d+)[:.]?\s*(.+?)(?=(?:Summary )?\d+[:.]|$)',
            r'Article \d+[:\s]*(.+?)(?=Article \d+|$)',
            r'(\d+\.\s*.+?)(?=\d+\.|$)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            if matches and len(matches) >= expected_count:
                summaries = []
                for match in matches[:expected_count]:
                    if isinstance(match, tuple):
                        summary = match[-1].strip()
                    else:
                        summary = match.strip()
                    summaries.append(summary[:300])  # Limit length
                return summaries
        
        # Final fallback: split by paragraphs or sentences
        sentences = text.split('\n')
        meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if len(meaningful_sentences) >= expected_count:
            return meaningful_sentences[:expected_count]
        
        # Return generic summaries if all else fails
        return [f"Summary not available for article {i+1}" for i in range(expected_count)]


class AIServiceManager:
    """Manages multiple AI service adapters with fallback and load balancing."""
    
    def __init__(self):
        self.adapters = {}
        self.primary_adapter = None
        self.usage_stats = {}
    
    def register_adapter(self, name: str, adapter: AIAdapter, is_primary: bool = False):
        """Register an AI adapter."""
        self.adapters[name] = adapter
        self.usage_stats[name] = {
            'requests': 0,
            'successes': 0,
            'failures': 0,
            'total_cost': 0.0
        }
        
        if is_primary or self.primary_adapter is None:
            self.primary_adapter = name
        
        logger.info(f"Registered {name} adapter (available: {adapter.is_available()})")
    
    def get_available_adapters(self) -> List[str]:
        """Get list of available adapters."""
        available = []
        for name, adapter in self.adapters.items():
            if adapter.is_available():
                available.append(name)
        return available
    
    def _execute_with_fallback(self, operation: str, *args, **kwargs) -> AIResponse:
        """Execute operation with fallback to other adapters if primary fails."""
        # Try primary adapter first
        if self.primary_adapter and self.primary_adapter in self.adapters:
            response = self._execute_operation(self.primary_adapter, operation, *args, **kwargs)
            if response.success:
                return response
            
            logger.warning(f"Primary adapter {self.primary_adapter} failed, trying fallbacks")
        
        # Try other available adapters
        for name, adapter in self.adapters.items():
            if name == self.primary_adapter:  # Skip primary, already tried
                continue
            
            if adapter.is_available():
                response = self._execute_operation(name, operation, *args, **kwargs)
                if response.success:
                    logger.info(f"Fallback successful with {name}")
                    return response
        
        # All adapters failed
        logger.error(f"All AI adapters failed for operation: {operation}")
        return AIResponse(
            content="",
            success=False,
            provider="None",
            model="None",
            error="All AI services unavailable"
        )
    
    def _execute_operation(self, adapter_name: str, operation: str, *args, **kwargs) -> AIResponse:
        """Execute operation on specific adapter and update stats."""
        adapter = self.adapters[adapter_name]
        stats = self.usage_stats[adapter_name]
        
        stats['requests'] += 1
        
        try:
            method = getattr(adapter, operation)
            response = method(*args, **kwargs)
            
            if response.success:
                stats['successes'] += 1
            else:
                stats['failures'] += 1
            
            stats['total_cost'] += response.cost_estimate
            
            return response
        
        except Exception as e:
            stats['failures'] += 1
            logger.error(f"Error executing {operation} on {adapter_name}: {e}")
            
            return AIResponse(
                content="",
                success=False,
                provider=adapter_name,
                model=adapter.model,
                error=str(e)
            )
    
    def classify_article(self, title: str, summary: str) -> AIResponse:
        """Classify article with fallback support."""
        return self._execute_with_fallback('classify_article', title, summary)
    
    def get_current_provider(self) -> str:
        """Get the name of the current primary provider."""
        return self.primary_adapter or 'unknown'
    
    def generate_summary(self, title: str, content: str) -> AIResponse:
        """Generate summary with fallback support."""
        return self._execute_with_fallback('generate_summary', title, content)
    
    def generate_batch_summaries(self, articles: List[Dict]) -> AIResponse:
        """Generate batch summaries with fallback support."""
        return self._execute_with_fallback('generate_batch_summaries', articles)
    
    def detect_trends(self, articles: List[Dict]) -> AIResponse:
        """Detect trends with fallback support."""
        return self._execute_with_fallback('detect_trends', articles)
    
    def get_usage_stats(self) -> Dict[str, Dict]:
        """Get usage statistics for all adapters."""
        return self.usage_stats.copy()
    
    def set_primary_adapter(self, name: str):
        """Set primary adapter."""
        if name in self.adapters:
            self.primary_adapter = name
            logger.info(f"Primary adapter set to: {name}")
        else:
            logger.error(f"Adapter {name} not found")


# Factory function for easy setup
def create_ai_manager(config: Dict[str, str] = None) -> AIServiceManager:
    """Create AI manager with configured adapters using centralized config."""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from config import AI_MODELS, PRIMARY_AI_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
    
    manager = AIServiceManager()
    
    # Use config parameter or fall back to centralized config
    if config is None:
        config = {
            'openai_key': OPENAI_API_KEY,
            'anthropic_key': ANTHROPIC_API_KEY,
            'google_key': GOOGLE_API_KEY,
        }
    
    # Get models from centralized config
    openai_model = config.get('openai_model', AI_MODELS['openai']['default'])
    anthropic_model = config.get('anthropic_model', AI_MODELS['anthropic']['default'])
    google_model = config.get('google_model', AI_MODELS['google']['default'])
    
    # Determine primary provider
    primary_provider = config.get('primary_provider', PRIMARY_AI_PROVIDER)
    
    # Register providers based on availability and primary preference
    registered_adapters = []
    
    # Register Google AI if available
    if config.get('google_key') and AI_MODELS['google']['enabled']:
        try:
            adapter = GoogleAIAdapter(config['google_key'], google_model)
            is_primary = primary_provider == 'google'
            manager.register_adapter('google', adapter, is_primary=is_primary)
            registered_adapters.append('google' + (' (primary)' if is_primary else ''))
        except ImportError as e:
            logger.warning(f"Google AI adapter not available: {e}")
    
    # Register OpenAI if available
    if config.get('openai_key') and AI_MODELS['openai']['enabled']:
        try:
            adapter = OpenAIAdapter(config['openai_key'], openai_model)
            is_primary = primary_provider == 'openai'
            manager.register_adapter('openai', adapter, is_primary=is_primary)
            registered_adapters.append('openai' + (' (primary)' if is_primary else ''))
        except ImportError as e:
            logger.warning(f"OpenAI adapter not available: {e}")
    
    # Register Anthropic if available
    if config.get('anthropic_key') and AI_MODELS['anthropic']['enabled']:
        try:
            adapter = AnthropicAdapter(config['anthropic_key'], anthropic_model)
            is_primary = primary_provider == 'anthropic'
            manager.register_adapter('anthropic', adapter, is_primary=is_primary)
            registered_adapters.append('anthropic' + (' (primary)' if is_primary else ''))
        except ImportError as e:
            logger.warning(f"Anthropic adapter not available: {e}")
    
    available = manager.get_available_adapters()
    logger.info(f"AI Manager initialized with {len(available)} available adapters: {registered_adapters}")
    
    return manager