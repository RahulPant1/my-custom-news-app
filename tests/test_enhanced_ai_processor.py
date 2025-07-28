"""Tests for enhanced AI processor."""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import DatabaseManager
from enhanced_ai_processor import EnhancedAIProcessor
from ai_adapters import AIResponse, AIServiceManager


class TestEnhancedAIProcessor:
    """Test enhanced AI processor functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        
        db_manager = DatabaseManager(temp_path)
        yield db_manager
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def mock_ai_manager(self):
        """Create mock AI manager."""
        manager = Mock(spec=AIServiceManager)
        manager.get_available_adapters.return_value = ['test_provider']
        manager.get_usage_stats.return_value = {
            'test_provider': {
                'requests': 0,
                'successes': 0,
                'failures': 0,
                'total_cost': 0.0
            }
        }
        return manager
    
    @pytest.fixture
    def processor(self, temp_db, mock_ai_manager):
        """Create enhanced AI processor with mocks."""
        with patch('enhanced_ai_processor.create_ai_manager') as mock_create:
            mock_create.return_value = mock_ai_manager
            
            processor = EnhancedAIProcessor(
                ai_config={'openai_key': 'test_key'}, 
                db_manager=temp_db
            )
            processor.ai_manager = mock_ai_manager
            return processor
    
    def test_processor_initialization(self, processor, mock_ai_manager):
        """Test processor initialization."""
        assert processor.ai_manager == mock_ai_manager
        assert processor.processing_stats['classified'] == 0
        assert processor.processing_stats['summarized'] == 0
        assert processor.processing_stats['api_calls'] == 0
    
    def test_classify_article_enhanced_success(self, processor, mock_ai_manager):
        """Test successful enhanced article classification."""
        # Mock successful AI response
        ai_response = AIResponse(
            content='["Technology & Gadgets", "Science & Discovery"]',
            success=True,
            provider='TestProvider',
            model='test-model',
            tokens_used=100,
            cost_estimate=0.01
        )
        mock_ai_manager.classify_article.return_value = ai_response
        
        categories = processor.classify_article_enhanced(
            "AI Breakthrough in Quantum Computing", 
            "Researchers achieve quantum supremacy"
        )
        
        assert categories == ["Technology & Gadgets", "Science & Discovery"]
        assert processor.processing_stats['classified'] == 1
        assert processor.processing_stats['api_calls'] == 1
        assert processor.processing_stats['total_cost'] == 0.01
    
    def test_classify_article_enhanced_with_existing(self, processor):
        """Test classification with existing valid categories."""
        existing_categories = ["Technology & Gadgets"]
        
        categories = processor.classify_article_enhanced(
            "Tech Article", 
            "Tech content",
            existing_categories
        )
        
        # Should return existing categories without API call
        assert categories == existing_categories
        assert processor.processing_stats['api_calls'] == 0
    
    def test_classify_article_enhanced_fallback(self, processor, mock_ai_manager):
        """Test classification fallback to rule-based."""
        # Mock AI failure
        ai_response = AIResponse(
            content='',
            success=False,
            provider='TestProvider',
            model='test-model',
            error='API failed'
        )
        mock_ai_manager.classify_article.return_value = ai_response
        
        categories = processor.classify_article_enhanced(
            "AI and Machine Learning Breakthrough", 
            "New artificial intelligence research"
        )
        
        # Should use rule-based classification
        assert len(categories) > 0
        assert processor.processing_stats['errors'] == 1
    
    def test_rule_based_classification(self, processor):
        """Test rule-based classification fallback."""
        # Test technology keywords
        tech_categories = processor._rule_based_classification(
            "New AI Software Released", 
            "Artificial intelligence application for smartphones"
        )
        assert "Technology & Gadgets" in tech_categories
        
        # Test health keywords
        health_categories = processor._rule_based_classification(
            "Medical Breakthrough in Treatment", 
            "New research from doctors shows health benefits"
        )
        assert "Health & Wellness" in health_categories
        
        # Test default fallback
        unknown_categories = processor._rule_based_classification(
            "Random Topic", 
            "Unrelated content without keywords"
        )
        assert len(unknown_categories) > 0  # Should return at least default category
    
    def test_generate_summary_enhanced_success(self, processor, mock_ai_manager):
        """Test successful enhanced summary generation."""
        ai_response = AIResponse(
            content='This is an AI-generated summary of the article.',
            success=True,
            provider='TestProvider',
            model='test-model',
            tokens_used=75,
            cost_estimate=0.005
        )
        mock_ai_manager.generate_summary.return_value = ai_response
        
        summary = processor.generate_summary_enhanced(
            "Test Article Title",
            "Long original content here...",
                        force_resummarize=True
        )
        
        assert summary == 'This is an AI-generated summary of the article.'
        assert processor.processing_stats['summarized'] == 1
        assert processor.processing_stats['api_calls'] == 1
    
    def test_generate_summary_enhanced_with_existing(self, processor):
        """Test summary generation with existing good summary."""
        existing_summary = "This is a good existing summary with enough content to be useful."
        
        summary = processor.generate_summary_enhanced(
            "Test Article",
            "Original content",
            existing_summary=existing_summary
        )
        
        # Should return existing summary without API call
        assert summary == existing_summary
        assert processor.processing_stats['api_calls'] == 0
    
    def test_generate_summary_enhanced_fallback(self, processor, mock_ai_manager):
        """Test summary generation fallback."""
        # Mock AI failure
        ai_response = AIResponse(
            content='',
            success=False,
            provider='TestProvider',
            model='test-model',
            error='Summary generation failed'
        )
        mock_ai_manager.generate_summary.return_value = ai_response
        
        original_summary = "This is the original article summary content."
        
        summary = processor.generate_summary_enhanced(
            "Test Article",
            original_summary,
                        force_resummarize=True
        )
        
        # Should return cleaned original summary
        assert summary == original_summary
        assert processor.processing_stats['errors'] == 1
    
    def test_fallback_summary(self, processor):
        """Test fallback summary generation."""
        # Test with good original content
        original = "This is a well-formatted original summary with good content."
        fallback = processor._fallback_summary("Test Title", original)
        assert fallback == original
        
        # Test with HTML content
        html_content = "<p>This has <strong>HTML</strong> tags.</p>"
        fallback = processor._fallback_summary("Test", html_content)
        assert "<p>" not in fallback
        assert "<strong>" not in fallback
        
        # Test with long content
        long_content = "A" * 300
        fallback = processor._fallback_summary("Test", long_content)
        assert len(fallback) <= 200
        assert fallback.endswith("...")
        
        # Test with no original content
        fallback = processor._fallback_summary("Test Title", "")
        assert "News about Test Title" in fallback
    
    def test_detect_trends_enhanced_success(self, processor, mock_ai_manager):
        """Test successful trend detection."""
        ai_response = AIResponse(
            content='{"Technology & Gadgets": ["AI development", "New processors"]}',
            success=True,
            provider='TestProvider',
            model='test-model',
            tokens_used=200,
            cost_estimate=0.02
        )
        mock_ai_manager.detect_trends.return_value = ai_response
        
        test_articles = [
            {
                'title': 'AI Breakthrough 1',
                'original_summary': 'AI development content'
            },
            {
                'title': 'AI Breakthrough 2', 
                'original_summary': 'More AI content'
            },
            {
                'title': 'Processor Update',
                'original_summary': 'New processor technology'
            },
            {
                'title': 'Another AI Story',
                'original_summary': 'Yet more AI news'
            },
            {
                'title': 'Tech Innovation',
                'original_summary': 'Technology innovation story'
            }
        ]
        
        trends = processor.detect_trends_enhanced(test_articles)
        
        assert "Technology & Gadgets" in trends
        assert "AI development" in trends["Technology & Gadgets"]
        assert processor.processing_stats['trends_detected'] == 2
    
    def test_detect_trends_enhanced_insufficient_articles(self, processor):
        """Test trend detection with insufficient articles."""
        few_articles = [
            {'title': 'Article 1', 'original_summary': 'Content 1'},
            {'title': 'Article 2', 'original_summary': 'Content 2'}
        ]
        
        trends = processor.detect_trends_enhanced(few_articles, min_articles=5)
        
        assert trends == {}
        assert processor.processing_stats['api_calls'] == 0
    
    def test_validate_trends(self, processor):
        """Test trend validation."""
        from config import AI_CATEGORIES
        
        # Valid trends
        valid_trends = {
            AI_CATEGORIES[0]: ["valid topic 1", "valid topic 2"],
            AI_CATEGORIES[1]: ["another topic"]
        }
        validated = processor._validate_trends(valid_trends)
        assert len(validated) == 2
        
        # Invalid category should be filtered out
        invalid_trends = {
            "Invalid Category": ["topic 1"],
            AI_CATEGORIES[0]: ["valid topic"]
        }
        validated = processor._validate_trends(invalid_trends)
        assert "Invalid Category" not in validated
        assert AI_CATEGORIES[0] in validated
        
        # Too many topics should be limited
        many_topics = {
            AI_CATEGORIES[0]: [f"topic {i}" for i in range(10)]
        }
        validated = processor._validate_trends(many_topics)
        assert len(validated[AI_CATEGORIES[0]]) == 5  # Limited to 5
    
    def test_simple_trend_detection(self, processor):
        """Test simple keyword-based trend detection."""
        articles = [
            {'title': 'AI Revolution Continues'},
            {'title': 'Machine Learning Breakthrough'},
            {'title': 'AI Development News'},
            {'title': 'Artificial Intelligence Update'},
            {'title': 'Technology Innovation'}
        ]
        
        trends = processor._simple_trend_detection(articles)
        
        # Should find common words
        assert len(trends) > 0
        if trends:  # If any trends found
            first_category = list(trends.keys())[0]
            assert isinstance(trends[first_category], list)
    
    def test_process_article_batch_enhanced(self, processor, mock_ai_manager):
        """Test enhanced batch processing."""
        # Mock AI responses
        mock_ai_manager.classify_article.return_value = AIResponse(
            content='["Technology & Gadgets"]',
            success=True,
            provider='TestProvider',
            model='test-model'
        )
        mock_ai_manager.generate_summary.return_value = AIResponse(
            content='AI-generated summary',
            success=True,
            provider='TestProvider',
            model='test-model'
        )
        
        test_articles = [
            {
                'id': 1,
                'title': 'Test Article 1',
                'original_summary': 'Original content 1'
            },
            {
                'id': 2,
                'title': 'Test Article 2',
                'original_summary': 'Original content 2'
            }
        ]
        
        processed_articles, stats = processor.process_article_batch_enhanced(test_articles)
        
        assert len(processed_articles) == 2
        assert stats['processed'] == 2
        assert stats['errors'] == 0
        
        # Check that articles were enhanced
        for article in processed_articles:
            assert 'ai_categories' in article
            assert 'ai_summary' in article
    
    def test_process_article_batch_skip_processed(self, processor):
        """Test batch processing skips already processed articles."""
        already_processed = [
            {
                'id': 1,
                'title': 'Processed Article',
                'original_summary': 'Content',
                'ai_categories': ['Technology & Gadgets'],
                'ai_summary': 'Existing summary'
            }
        ]
        
        processed_articles, stats = processor.process_article_batch_enhanced(already_processed)
        
        assert len(processed_articles) == 1
        assert stats['skipped'] == 1
        assert stats['processed'] == 0
    
    def test_process_article_batch_error_handling(self, processor, mock_ai_manager):
        """Test batch processing error handling."""
        # Mock AI to raise exception
        mock_ai_manager.classify_article.side_effect = Exception("AI service error")
        
        test_articles = [
            {
                'id': 1,
                'title': 'Error Article',
                'original_summary': 'Content'
            }
        ]
        
        processed_articles, stats = processor.process_article_batch_enhanced(test_articles)
        
        assert len(processed_articles) == 1
        assert stats['errors'] == 1
        
        # Article should have fallback data
        article = processed_articles[0]
        assert 'ai_categories' in article
        assert 'ai_summary' in article
    
    def test_get_processing_stats(self, processor, mock_ai_manager):
        """Test getting comprehensive processing statistics."""
        # Set some stats
        processor.processing_stats['classified'] = 10
        processor.processing_stats['api_calls'] = 15
        processor.processing_stats['total_cost'] = 0.25
        
        stats = processor.get_processing_stats()
        
        assert 'processing_stats' in stats
        assert 'ai_service_stats' in stats
        assert 'available_adapters' in stats
        
        assert stats['processing_stats']['classified'] == 10
        assert stats['processing_stats']['api_calls'] == 15
        assert stats['processing_stats']['total_cost'] == 0.25
    
    def test_run_enhanced_processing_cycle(self, processor, mock_ai_manager):
        """Test complete enhanced processing cycle."""
        # Add test articles to database
        processor.db_manager.insert_article({
            'title': 'Unprocessed Article 1',
            'original_summary': 'Content that needs AI processing',
            'source_link': 'http://example.com/1',
            'content_hash': 'hash1'
        })
        
        processor.db_manager.insert_article({
            'title': 'Unprocessed Article 2', 
            'original_summary': 'More content for processing',
            'source_link': 'http://example.com/2',
            'content_hash': 'hash2'
        })
        
        # Mock AI responses
        mock_ai_manager.classify_article.return_value = AIResponse(
            content='["Technology & Gadgets"]',
            success=True,
            provider='TestProvider',
            model='test-model'
        )
        mock_ai_manager.generate_summary.return_value = AIResponse(
            content='AI summary',
            success=True,
            provider='TestProvider',
            model='test-model'
        )
        mock_ai_manager.detect_trends.return_value = AIResponse(
            content='{"Technology & Gadgets": ["AI trends"]}',
            success=True,
            provider='TestProvider',
            model='test-model'
        )
        
        # Run processing cycle
        final_stats = processor.run_enhanced_processing_cycle()
        
        assert 'processed' in final_stats
        assert 'updated' in final_stats
        assert 'trends' in final_stats
        assert final_stats['processed'] > 0
    
    def test_run_enhanced_processing_no_articles(self, processor):
        """Test processing cycle with no articles to process."""
        final_stats = processor.run_enhanced_processing_cycle()
        
        assert final_stats['processed'] == 0
        assert final_stats['updated'] == 0
        assert final_stats['trends'] == 0