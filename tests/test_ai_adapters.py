"""Tests for AI adapters and multi-API functionality."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import time

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_adapters import (
    AIAdapter, AIResponse, OpenAIAdapter, AnthropicAdapter, 
    GoogleAIAdapter, AIServiceManager, create_ai_manager
)
from config import AI_CATEGORIES


class TestAIResponse:
    """Test AIResponse dataclass."""
    
    def test_ai_response_creation(self):
        """Test creating AIResponse objects."""
        response = AIResponse(
            content="test content",
            success=True,
            provider="TestProvider",
            model="test-model",
            tokens_used=100,
            cost_estimate=0.01
        )
        
        assert response.content == "test content"
        assert response.success is True
        assert response.provider == "TestProvider"
        assert response.model == "test-model"
        assert response.tokens_used == 100
        assert response.cost_estimate == 0.01
        assert response.error is None
    
    def test_ai_response_with_error(self):
        """Test AIResponse with error."""
        response = AIResponse(
            content="",
            success=False,
            provider="TestProvider",
            model="test-model",
            error="Test error message"
        )
        
        assert response.success is False
        assert response.error == "Test error message"


class TestAIAdapter:
    """Test base AIAdapter functionality."""
    
    class MockAdapter(AIAdapter):
        """Mock adapter for testing."""
        
        def classify_article(self, title, summary):
            return AIResponse("test", True, "Mock", "mock-model")
        
        def generate_summary(self, title, content):
            return AIResponse("test summary", True, "Mock", "mock-model")
        
        def detect_trends(self, articles):
            return AIResponse("{}", True, "Mock", "mock-model")
        
        def is_available(self):
            return True
    
    def test_adapter_initialization(self):
        """Test adapter initialization."""
        adapter = self.MockAdapter("test-key", "test-model")
        
        assert adapter.api_key == "test-key"
        assert adapter.model == "test-model"
        assert adapter.provider_name == "Mock"
        assert adapter.rate_limit_delay == 1.0
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        adapter = self.MockAdapter("test-key", "test-model")
        adapter.rate_limit_delay = 0.1  # Short delay for testing
        
        start_time = time.time()
        adapter._rate_limit()
        adapter._rate_limit()  # Should cause delay
        elapsed = time.time() - start_time
        
        # Should take at least the rate limit delay
        assert elapsed >= 0.1


class TestOpenAIAdapter:
    """Test OpenAI adapter."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        with patch('ai_adapters.openai') as mock_openai:
            mock_client = Mock()
            mock_openai.OpenAI.return_value = mock_client
            yield mock_client
    
    def test_openai_adapter_initialization(self, mock_openai_client):
        """Test OpenAI adapter initialization."""
        with patch('ai_adapters.openai', Mock()):
            adapter = OpenAIAdapter("test-key", "gpt-3.5-turbo")
            assert adapter.api_key == "test-key"
            assert adapter.model == "gpt-3.5-turbo"
    
    def test_openai_classify_article_success(self, mock_openai_client):
        """Test successful OpenAI article classification."""
        # Mock successful response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(["Technology & Gadgets"])
        mock_response.usage.total_tokens = 150
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with patch('ai_adapters.openai', Mock()):
            adapter = OpenAIAdapter("test-key")
            adapter.client = mock_openai_client
            
            response = adapter.classify_article("Test AI Article", "Article about artificial intelligence")
            
            assert response.success is True
            assert response.provider == "OpenAI"
            assert response.tokens_used == 150
            
            categories = json.loads(response.content)
            assert "Technology & Gadgets" in categories
    
    def test_openai_classify_article_fallback_parsing(self, mock_openai_client):
        """Test OpenAI classification with fallback parsing."""
        # Mock response with invalid JSON but containing category names
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "The article is about Technology & Gadgets and Science"
        mock_response.usage.total_tokens = 100
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with patch('ai_adapters.openai', Mock()):
            adapter = OpenAIAdapter("test-key")
            adapter.client = mock_openai_client
            
            response = adapter.classify_article("Test Article", "Test content")
            
            assert response.success is True
            categories = json.loads(response.content)
            assert "Technology & Gadgets" in categories
    
    def test_openai_generate_summary_success(self, mock_openai_client):
        """Test successful OpenAI summary generation."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is a generated summary."
        mock_response.usage.total_tokens = 75
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with patch('ai_adapters.openai', Mock()):
            adapter = OpenAIAdapter("test-key")
            adapter.client = mock_openai_client
            
            response = adapter.generate_summary("Test Title", "Long article content here...")
            
            assert response.success is True
            assert response.content == "This is a generated summary."
            assert response.tokens_used == 75
    
    def test_openai_detect_trends_success(self, mock_openai_client):
        """Test successful OpenAI trend detection."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "Technology & Gadgets": ["AI development", "New processors"]
        })
        mock_response.usage.total_tokens = 200
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with patch('ai_adapters.openai', Mock()):
            adapter = OpenAIAdapter("test-key")
            adapter.client = mock_openai_client
            
            test_articles = [
                {"title": "AI Breakthrough", "original_summary": "New AI technology"},
                {"title": "Processor Update", "original_summary": "Faster processors released"},
                {"title": "Another AI Story", "original_summary": "Yet more AI news"}
            ]
            
            response = adapter.detect_trends(test_articles)
            
            assert response.success is True
            trends = json.loads(response.content)
            assert "Technology & Gadgets" in trends
            assert "AI development" in trends["Technology & Gadgets"]
    
    def test_openai_error_handling(self, mock_openai_client):
        """Test OpenAI error handling."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        with patch('ai_adapters.openai', Mock()):
            adapter = OpenAIAdapter("test-key")
            adapter.client = mock_openai_client
            
            response = adapter.classify_article("Test", "Content")
            
            assert response.success is False
            assert response.error == "API Error"
            # Should fallback to first category
            categories = json.loads(response.content)
            assert categories == [AI_CATEGORIES[0]]
    
    def test_openai_cost_estimation(self):
        """Test OpenAI cost estimation."""
        with patch('ai_adapters.openai', Mock()):
            adapter = OpenAIAdapter("test-key", "gpt-4")
            cost_gpt4 = adapter._estimate_cost(1000)
            
            adapter_gpt35 = OpenAIAdapter("test-key", "gpt-3.5-turbo")
            cost_gpt35 = adapter_gpt35._estimate_cost(1000)
            
            # GPT-4 should be more expensive
            assert cost_gpt4 > cost_gpt35


class TestAnthropicAdapter:
    """Test Anthropic adapter."""
    
    @pytest.fixture
    def mock_anthropic_client(self):
        """Mock Anthropic client."""
        with patch('ai_adapters.anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.Anthropic.return_value = mock_client
            yield mock_client
    
    def test_anthropic_adapter_initialization(self, mock_anthropic_client):
        """Test Anthropic adapter initialization."""
        with patch('ai_adapters.anthropic', Mock()):
            adapter = AnthropicAdapter("test-key", "claude-3-haiku-20240307")
            assert adapter.api_key == "test-key"
            assert adapter.model == "claude-3-haiku-20240307"
    
    def test_anthropic_classify_article_success(self, mock_anthropic_client):
        """Test successful Anthropic classification."""
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps(["Science & Discovery"])
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        
        mock_anthropic_client.messages.create.return_value = mock_response
        
        with patch('ai_adapters.anthropic', Mock()):
            adapter = AnthropicAdapter("test-key")
            adapter.client = mock_anthropic_client
            
            response = adapter.classify_article("Science Article", "Research content")
            
            assert response.success is True
            assert response.provider == "Anthropic"
            assert response.tokens_used == 150  # input + output
            
            categories = json.loads(response.content)
            assert "Science & Discovery" in categories


class TestGoogleAIAdapter:
    """Test Google AI adapter."""
    
    @pytest.fixture
    def mock_google_ai(self):
        """Mock Google AI."""
        with patch('ai_adapters.genai') as mock_genai:
            mock_model = Mock()
            mock_genai.GenerativeModel.return_value = mock_model
            yield mock_model
    
    def test_google_ai_adapter_initialization(self, mock_google_ai):
        """Test Google AI adapter initialization."""
        with patch('ai_adapters.genai', Mock()) as mock_genai:
            adapter = GoogleAIAdapter("test-key", "gemini-pro")
            assert adapter.api_key == "test-key"
            assert adapter.model == "gemini-pro"
    
    def test_google_ai_classify_article_success(self, mock_google_ai):
        """Test successful Google AI classification."""
        mock_response = Mock()
        mock_response.text = json.dumps(["Business & Finance"])
        
        mock_google_ai.generate_content.return_value = mock_response
        
        with patch('ai_adapters.genai', Mock()):
            adapter = GoogleAIAdapter("test-key")
            adapter.model_instance = mock_google_ai
            
            response = adapter.classify_article("Business Article", "Market update")
            
            assert response.success is True
            assert response.provider == "GoogleAI"
            
            categories = json.loads(response.content)
            assert "Business & Finance" in categories


class TestAIServiceManager:
    """Test AI service manager."""
    
    def test_manager_initialization(self):
        """Test AI service manager initialization."""
        manager = AIServiceManager()
        
        assert manager.adapters == {}
        assert manager.primary_adapter is None
        assert manager.usage_stats == {}
    
    def test_register_adapter(self):
        """Test adapter registration."""
        manager = AIServiceManager()
        
        class MockAdapter(AIAdapter):
            def classify_article(self, title, summary):
                return AIResponse("test", True, "Mock", "mock")
            def generate_summary(self, title, content):
                return AIResponse("test", True, "Mock", "mock")
            def detect_trends(self, articles):
                return AIResponse("{}", True, "Mock", "mock")
            def is_available(self):
                return True
        
        adapter = MockAdapter("test-key")
        manager.register_adapter("test_adapter", adapter, is_primary=True)
        
        assert "test_adapter" in manager.adapters
        assert manager.primary_adapter == "test_adapter"
        assert "test_adapter" in manager.usage_stats
    
    def test_execute_with_fallback_success(self):
        """Test successful execution with primary adapter."""
        manager = AIServiceManager()
        
        class MockAdapter(AIAdapter):
            def classify_article(self, title, summary):
                return AIResponse("test", True, "Mock", "mock")
            def generate_summary(self, title, content):
                return AIResponse("test", True, "Mock", "mock")
            def detect_trends(self, articles):
                return AIResponse("{}", True, "Mock", "mock")
            def is_available(self):
                return True
        
        adapter = MockAdapter("test-key")
        manager.register_adapter("primary", adapter, is_primary=True)
        
        response = manager.classify_article("Test", "Content")
        
        assert response.success is True
        assert response.content == "test"
        
        # Check stats were updated
        stats = manager.get_usage_stats()
        assert stats["primary"]["requests"] == 1
        assert stats["primary"]["successes"] == 1
    
    def test_execute_with_fallback_failure(self):
        """Test fallback when primary adapter fails."""
        manager = AIServiceManager()
        
        class FailingAdapter(AIAdapter):
            def classify_article(self, title, summary):
                return AIResponse("", False, "Failing", "failing", error="Primary failed")
            def generate_summary(self, title, content):
                return AIResponse("", False, "Failing", "failing", error="Primary failed")
            def detect_trends(self, articles):
                return AIResponse("{}", False, "Failing", "failing", error="Primary failed")
            def is_available(self):
                return True
        
        class WorkingAdapter(AIAdapter):
            def classify_article(self, title, summary):
                return AIResponse("fallback", True, "Working", "working")
            def generate_summary(self, title, content):
                return AIResponse("fallback", True, "Working", "working")
            def detect_trends(self, articles):
                return AIResponse("{}", True, "Working", "working")
            def is_available(self):
                return True
        
        primary = FailingAdapter("key1")
        fallback = WorkingAdapter("key2")
        
        manager.register_adapter("primary", primary, is_primary=True)
        manager.register_adapter("fallback", fallback)
        
        response = manager.classify_article("Test", "Content")
        
        assert response.success is True
        assert response.content == "fallback"
        assert response.provider == "Working"
        
        # Check that both adapters were tried
        stats = manager.get_usage_stats()
        assert stats["primary"]["failures"] == 1
        assert stats["fallback"]["successes"] == 1
    
    def test_get_available_adapters(self):
        """Test getting available adapters."""
        manager = AIServiceManager()
        
        class AvailableAdapter(AIAdapter):
            def classify_article(self, title, summary): pass
            def generate_summary(self, title, content): pass
            def detect_trends(self, articles): pass
            def is_available(self):
                return True
        
        class UnavailableAdapter(AIAdapter):
            def classify_article(self, title, summary): pass
            def generate_summary(self, title, content): pass
            def detect_trends(self, articles): pass
            def is_available(self):
                return False
        
        manager.register_adapter("available", AvailableAdapter("key1"))
        manager.register_adapter("unavailable", UnavailableAdapter("key2"))
        
        available = manager.get_available_adapters()
        
        assert "available" in available
        assert "unavailable" not in available
    
    def test_set_primary_adapter(self):
        """Test setting primary adapter."""
        manager = AIServiceManager()
        
        class MockAdapter(AIAdapter):
            def classify_article(self, title, summary): pass
            def generate_summary(self, title, content): pass
            def detect_trends(self, articles): pass
            def is_available(self):
                return True
        
        adapter1 = MockAdapter("key1")
        adapter2 = MockAdapter("key2")
        
        manager.register_adapter("adapter1", adapter1, is_primary=True)
        manager.register_adapter("adapter2", adapter2)
        
        assert manager.primary_adapter == "adapter1"
        
        manager.set_primary_adapter("adapter2")
        assert manager.primary_adapter == "adapter2"


class TestCreateAIManager:
    """Test AI manager factory function."""
    
    def test_create_ai_manager_empty_config(self):
        """Test creating AI manager with empty config."""
        config = {}
        manager = create_ai_manager(config)
        
        assert isinstance(manager, AIServiceManager)
        assert len(manager.adapters) == 0
    
    @patch('ai_adapters.openai', Mock())
    def test_create_ai_manager_with_openai(self):
        """Test creating AI manager with OpenAI config."""
        config = {
            'openai_key': 'test-openai-key',
            'openai_model': 'gpt-4'
        }
        
        with patch('ai_adapters.OpenAIAdapter') as mock_adapter_class:
            mock_adapter = Mock()
            mock_adapter_class.return_value = mock_adapter
            
            manager = create_ai_manager(config)
            
            # Should register OpenAI adapter
            mock_adapter_class.assert_called_once_with('test-openai-key', 'gpt-4')
    
    def test_create_ai_manager_missing_libraries(self):
        """Test creating AI manager when libraries are missing."""
        config = {
            'openai_key': 'test-key'
        }
        
        # Mock ImportError for OpenAI
        with patch('ai_adapters.OpenAIAdapter', side_effect=ImportError("OpenAI not installed")):
            manager = create_ai_manager(config)
            
            # Should still create manager, just without the adapter
            assert isinstance(manager, AIServiceManager)
            assert len(manager.adapters) == 0