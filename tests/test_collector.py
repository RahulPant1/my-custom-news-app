"""Tests for article collector module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from collector import ArticleCollector
from database import DatabaseManager


class TestArticleCollector:
    
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
    def collector(self, temp_db):
        """Create collector with temporary database."""
        return ArticleCollector(temp_db)
    
    def test_generate_content_hash(self, collector):
        """Test content hash generation."""
        hash1 = collector.generate_content_hash("Test Title", "Test content")
        hash2 = collector.generate_content_hash("Test Title", "Test content")
        hash3 = collector.generate_content_hash("Different Title", "Test content")
        
        # Same content should produce same hash
        assert hash1 == hash2
        
        # Different content should produce different hash
        assert hash1 != hash3
        
        # Hash should be consistent
        assert len(hash1) == 32  # MD5 hash length
    
    def test_extract_article_data(self, collector):
        """Test article data extraction from RSS entry."""
        # Mock RSS entry
        mock_entry = Mock()
        mock_entry.title = "Test Article Title"
        mock_entry.author = "Test Author"
        mock_entry.link = "https://example.com/article"
        mock_entry.summary = "This is a test article summary."
        mock_entry.published_parsed = (2024, 1, 1, 10, 30, 0, 0, 1, 0)
        del mock_entry.content
        
        article_data = collector.extract_article_data(mock_entry, "Technology")
        
        assert article_data['title'] == "Test Article Title"
        assert article_data['author'] == "Test Author"
        assert article_data['source_link'] == "https://example.com/article"
        assert article_data['original_summary'] == "This is a test article summary."
        assert article_data['rss_category'] == "Technology"
        assert article_data['publication_date'] == "2024-01-01T10:30:00"
        assert 'content_hash' in article_data
    
    def test_extract_article_data_minimal(self, collector):
        """Test article data extraction with minimal entry data."""
        # Mock minimal RSS entry
        mock_entry = Mock()
        mock_entry.title = "Minimal Article"
        mock_entry.link = "https://example.com/minimal"
        
        # Remove optional attributes
        del mock_entry.author
        del mock_entry.summary
        del mock_entry.published_parsed
        
        article_data = collector.extract_article_data(mock_entry, "Science")
        
        assert article_data['title'] == "Minimal Article"
        assert article_data['author'] is None
        assert article_data['source_link'] == "https://example.com/minimal"
        assert article_data['rss_category'] == "Science"
        assert article_data['publication_date'] is None
    
    @patch('collector.feedparser')
    def test_fetch_from_rss_feed_success(self, mock_feedparser, collector):
        """Test successful RSS feed fetching."""
        with patch.object(collector.session, 'get') as mock_get:
            # Mock response
            mock_response = Mock()
            mock_response.content = b"<rss>mock content</rss>"
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # Mock feed parsing
            mock_feed = Mock()
            mock_feed.bozo = False
            
            mock_entry = Mock()
            mock_entry.title = "Test Article"
            mock_entry.link = "https://example.com/test1"
            mock_entry.summary = "Test summary"
            
            mock_feed.entries = [mock_entry]
            mock_feedparser.parse.return_value = mock_feed
            
            articles = collector.fetch_from_rss_feed("https://example.com/feed", "Technology")
            
            assert len(articles) == 1
            assert articles[0]['title'] == "Test Article"
            assert articles[0]['rss_category'] == "Technology"
    
    def test_deduplicate_articles(self, collector):
        """Test article deduplication."""
        articles = [
            {
                'title': 'Article 1',
                'content_hash': 'hash1',
                'source_link': 'https://example.com/1'
            },
            {
                'title': 'Article 2',
                'content_hash': 'hash2',
                'source_link': 'https://example.com/2'
            },
            {
                'title': 'Article 1 Duplicate',
                'content_hash': 'hash1',  # Same hash as first article
                'source_link': 'https://example.com/1-duplicate'
            },
            {
                'title': 'Article 3',
                'content_hash': 'hash3',
                'source_link': 'https://example.com/3'
            }
        ]
        
        unique_articles = collector.deduplicate_articles(articles)
        
        assert len(unique_articles) == 3
        
        # Check that the duplicate was removed (should keep first occurrence)
        titles = [a['title'] for a in unique_articles]
        assert 'Article 1' in titles
        assert 'Article 1 Duplicate' not in titles
    
    def test_balance_source_diversity(self, collector):
        """Test source diversity balancing."""
        articles = []
        
        # Create 10 articles from example.com (should be limited)
        for i in range(10):
            articles.append({
                'title': f'Example Article {i}',
                'source_link': f'https://example.com/article{i}',
                'content_hash': f'hash_example_{i}'
            })
        
        # Create 3 articles from different.com (should all be kept)
        for i in range(3):
            articles.append({
                'title': f'Different Article {i}',
                'source_link': f'https://different.com/article{i}',
                'content_hash': f'hash_different_{i}'
            })
        
        balanced_articles = collector.balance_source_diversity(articles, max_per_domain=5)
        
        # Should have 5 from example.com + 3 from different.com = 8 total
        assert len(balanced_articles) == 8
        
        # Count by domain
        example_com_count = sum(1 for a in balanced_articles if 'example.com' in a['source_link'])
        different_com_count = sum(1 for a in balanced_articles if 'different.com' in a['source_link'])
        
        assert example_com_count == 5  # Limited to max_per_domain
        assert different_com_count == 3  # All kept (under limit)
    
    def test_store_articles(self, collector):
        """Test article storage in database."""
        articles = [
            {
                'title': 'Storage Test 1',
                'source_link': 'https://example.com/storage1',
                'content_hash': 'storage_hash1'
            },
            {
                'title': 'Storage Test 2',
                'source_link': 'https://example.com/storage2',
                'content_hash': 'storage_hash2'
            }
        ]
        
        stats = collector.store_articles(articles)
        
        assert stats['stored'] == 2
        assert stats['skipped'] == 0
        assert stats['errors'] == 0
        
        # Verify articles were stored
        db_count = collector.db_manager.get_article_count()
        assert db_count == 2
    
    def test_store_articles_with_duplicates(self, collector):
        """Test article storage with duplicates."""
        # First, store an article
        article1 = {
            'title': 'Duplicate Test',
            'source_link': 'https://example.com/duplicate',
            'content_hash': 'duplicate_hash'
        }
        
        collector.db_manager.insert_article(article1)
        
        # Now try to store the same article again
        articles = [article1]  # Same article
        stats = collector.store_articles(articles)
        
        # Should be updated, not stored
        assert stats['stored'] == 0
        assert stats['updated'] == 1
        assert stats['skipped'] == 0
        assert stats['errors'] == 0
    
    @patch.object(ArticleCollector, 'collect_from_all_categories')
    @patch.object(ArticleCollector, 'deduplicate_articles')
    @patch.object(ArticleCollector, 'balance_source_diversity')
    @patch.object(ArticleCollector, 'store_articles')
    def test_run_collection_cycle(self, mock_store, mock_balance, mock_dedupe, mock_collect, collector):
        """Test complete collection cycle."""
        # Setup mocks
        raw_articles = [{'title': 'Raw 1'}, {'title': 'Raw 2'}, {'title': 'Raw 3'}]
        unique_articles = [{'title': 'Unique 1'}, {'title': 'Unique 2'}]
        balanced_articles = [{'title': 'Balanced 1'}]
        storage_stats = {'stored': 1, 'skipped': 0, 'errors': 0}
        
        mock_collect.return_value = raw_articles
        mock_dedupe.return_value = unique_articles
        mock_balance.return_value = balanced_articles
        mock_store.return_value = storage_stats
        
        # Run collection cycle
        final_stats = collector.run_collection_cycle()
        
        # Verify all steps were called
        mock_collect.assert_called_once_with(10)  # default max_per_feed
        mock_dedupe.assert_called_once_with(raw_articles)
        mock_balance.assert_called_once_with(unique_articles)
        mock_store.assert_called_once_with(balanced_articles)
        
        # Check final stats
        assert final_stats['collected'] == 3
        assert final_stats['unique'] == 2
        assert final_stats['balanced'] == 1
        assert final_stats['stored'] == 1
    
    def test_processed_urls_tracking(self, collector):
        """Test that processed URLs are tracked to avoid duplicates."""
        # Initially empty
        assert len(collector.processed_urls) == 0
        
        # Mock entry with URL
        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/test"
        mock_entry.summary = "Test summary"
        
        # Extract article data (should add URL to processed set)
        article_data = collector.extract_article_data(mock_entry, "Technology")
        collector.processed_urls.add(article_data['source_link'])
        
        assert len(collector.processed_urls) == 1
        assert "https://example.com/test" in collector.processed_urls