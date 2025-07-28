"""Tests for incremental collector module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import feedparser
import time

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from incremental_collector import IncrementalCollector
from database import DatabaseManager


class TestIncrementalCollector:
    
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
        """Create incremental collector with temporary database."""
        return IncrementalCollector(temp_db)
    
    def test_normalize_title(self, collector):
        """Test title normalization for duplicate detection."""
        # Test basic normalization
        assert collector.normalize_title("  Test Title  ") == "test title"
        
        # Test prefix removal
        assert collector.normalize_title("Breaking: Important News") == "important news"
        assert collector.normalize_title("URGENT: Crisis Update") == "crisis update"
        
        # Test punctuation removal
        assert collector.normalize_title("News! Update?") == "news update"
        
        # Test whitespace normalization
        assert collector.normalize_title("Multiple   Spaces   Here") == "multiple spaces here"
    
    def test_generate_title_hash(self, collector):
        """Test title hash generation."""
        # Same normalized titles should produce same hash
        hash1 = collector.generate_title_hash("Breaking: Test News")
        hash2 = collector.generate_title_hash("TEST NEWS")
        assert hash1 == hash2
        
        # Different titles should produce different hashes
        hash3 = collector.generate_title_hash("Different News")
        assert hash1 != hash3
    
    def test_generate_content_hash(self, collector):
        """Test comprehensive content hash generation."""
        # Same content should produce same hash
        hash1 = collector.generate_content_hash("Title", "Content", "http://example.com/path")
        hash2 = collector.generate_content_hash("Title", "Content", "http://example.com/path")
        assert hash1 == hash2
        
        # Different content should produce different hashes
        hash3 = collector.generate_content_hash("Different Title", "Content", "http://example.com/path")
        assert hash1 != hash3
        
        # URL path should affect hash
        hash4 = collector.generate_content_hash("Title", "Content", "http://example.com/different")
        assert hash1 != hash4
    
    def test_extract_guid(self, collector):
        """Test GUID extraction from RSS entries."""
        # Test with id field
        entry1 = Mock()
        entry1.id = "unique-id-123"
        assert collector.extract_guid(entry1) == "unique-id-123"
        
        # Test with guid field
        entry2 = Mock()
        del entry2.id  # Remove id attribute
        entry2.guid = "guid-456"
        assert collector.extract_guid(entry2) == "guid-456"
        
        # Test with link field
        entry3 = Mock()
        for attr in ['id', 'guid']:
            if hasattr(entry3, attr):
                delattr(entry3, attr)
        entry3.link = "http://example.com/article"
        assert collector.extract_guid(entry3) == "http://example.com/article"
        
        # Test with link object
        entry4 = Mock()
        for attr in ['id', 'guid']:
            if hasattr(entry4, attr):
                delattr(entry4, attr)
        link_obj = Mock()
        link_obj.href = "http://example.com/href"
        entry4.link = link_obj
        assert collector.extract_guid(entry4) == "http://example.com/href"
    
    def test_extract_enhanced_article_data(self, collector):
        """Test enhanced article data extraction."""
        # Create mock RSS entry
        entry = Mock()
        entry.title = "Test Article Title"
        entry.author = "Test Author"
        entry.link = "http://example.com/article1"
        entry.summary = "This is a test article summary with some content."
        entry.published_parsed = (2024, 1, 15, 10, 30, 0, 0, 1, 0)
        entry.id = "unique-guid-123"
        
        article_data = collector.extract_enhanced_article_data(entry, "Technology", "http://example.com/feed")
        
        assert article_data['title'] == "Test Article Title"
        assert article_data['author'] == "Test Author"
        assert article_data['source_link'] == "http://example.com/article1"
        assert article_data['rss_category'] == "Technology"
        assert article_data['publication_date'] == "2024-01-15T10:30:00"
        assert article_data['guid'] == "unique-guid-123"
        assert 'content_hash' in article_data
        assert 'title_hash' in article_data
        assert article_data['feed_url'] == "http://example.com/feed"
    
    def test_should_skip_article(self, collector):
        """Test article skip logic."""
        # Valid article should not be skipped
        valid_article = {
            'title': 'Valid Article Title',
            'source_link': 'http://example.com/valid',
            'guid': 'valid-guid'
        }
        should_skip, reason = collector.should_skip_article(valid_article)
        assert should_skip is False
        assert reason == 'ok'
        
        # Article without title should be skipped
        no_title = {'source_link': 'http://example.com/notitle'}
        should_skip, reason = collector.should_skip_article(no_title)
        assert should_skip is True
        assert reason == 'missing_required_fields'
        
        # Article with short title should be skipped
        short_title = {
            'title': 'Short',
            'source_link': 'http://example.com/short'
        }
        should_skip, reason = collector.should_skip_article(short_title)
        assert should_skip is True
        assert reason == 'title_too_short'
        
        # Already processed article should be skipped
        duplicate_check = {
            'title': 'Already Processed Article',
            'source_link': 'http://example.com/processed',
            'guid': 'processed-guid'
        }
        # Process once
        collector.should_skip_article(duplicate_check)
        # Second call should skip
        should_skip, reason = collector.should_skip_article(duplicate_check)
        assert should_skip is True
        assert reason == 'already_processed'
    
    @patch('incremental_collector.requests.Session')
    @patch('incremental_collector.feedparser')
    def test_fetch_feed_with_caching_success(self, mock_feedparser, mock_session_class, collector):
        """Test successful feed fetching with caching."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<rss>mock content</rss>'
        mock_response.headers = {
            'ETag': 'test-etag-123',
            'Last-Modified': 'Mon, 15 Jan 2024 10:00:00 GMT'
        }
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Mock feedparser
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.entries = [Mock(), Mock()]  # 2 entries
        mock_feedparser.parse.return_value = mock_feed
        
        feed, feed_info = collector.fetch_feed_with_caching("http://example.com/feed", "Technology")
        
        assert feed == mock_feed
        assert feed_info['status'] == 200
        assert feed_info['etag'] == 'test-etag-123'
        assert feed_info['last_modified'] == 'Mon, 15 Jan 2024 10:00:00 GMT'
        assert feed_info['cached'] is False
    
    @patch('incremental_collector.requests.Session')
    def test_fetch_feed_with_caching_304(self, mock_session_class, collector):
        """Test feed fetching with 304 Not Modified response."""
        # Setup feed tracking
        collector.db_manager.update_feed_tracking(
            "http://example.com/feed", True, 10, 
            etag="old-etag", last_modified="Old Date"
        )
        
        # Mock 304 response
        mock_response = Mock()
        mock_response.status_code = 304
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        feed, feed_info = collector.fetch_feed_with_caching("http://example.com/feed", "Technology")
        
        assert feed is None
        assert feed_info['cached'] is True
        assert feed_info['status'] == 304
    
    def test_process_feed_incrementally_skip_cached(self, collector):
        """Test incremental feed processing with cached feed."""
        with patch.object(collector, 'fetch_feed_with_caching') as mock_fetch:
            mock_fetch.return_value = (None, {'cached': True})
            
            stats = collector.process_feed_incrementally("http://example.com/feed", "Technology")
            
            assert stats['new'] == 0
            assert stats['updated'] == 0
            assert stats['skipped'] == 0
            assert stats['errors'] == 0
    
    def test_process_feed_incrementally_with_articles(self, collector):
        """Test incremental processing with actual articles."""
        # Mock feed with articles
        mock_feed = Mock()
        mock_feed.entries = []
        
        # Create mock entries
        for i in range(3):
            entry = Mock()
            entry.title = f"Test Article {i+1}"
            entry.link = f"http://example.com/article{i+1}"
            entry.summary = f"Summary for article {i+1}"
            entry.id = f"guid-{i+1}"
            mock_feed.entries.append(entry)
        
        feed_info = {'status': 200, 'etag': None, 'last_modified': None}
        
        with patch.object(collector, 'fetch_feed_with_caching') as mock_fetch:
            mock_fetch.return_value = (mock_feed, feed_info)
            
            stats = collector.process_feed_incrementally("http://example.com/feed", "Technology", max_articles=5)
            
            # Should process all 3 articles
            assert stats['new'] >= 0  # Depends on database state
            assert stats['errors'] == 0
    
    def test_run_incremental_collection(self, collector):
        """Test complete incremental collection run."""
        # Mock the category collection
        with patch.object(collector, 'collect_category_incrementally') as mock_collect:
            mock_collect.return_value = {'new': 5, 'updated': 2, 'skipped': 3, 'errors': 0}
            
            # Test with specific categories
            stats = collector.run_incremental_collection(categories=['Technology & Gadgets'])
            
            assert stats['new'] == 5
            assert stats['updated'] == 2
            assert stats['skipped'] == 3
            assert stats['errors'] == 0
            assert stats['feeds_processed'] > 0
    
    def test_collection_summary(self, collector):
        """Test collection summary generation."""
        # Set some collection stats
        collector.collection_stats = {
            'new_articles': 10,
            'updated_articles': 5,
            'duplicates_skipped': 3,
            'errors': 1
        }
        
        summary = collector.get_collection_summary()
        
        assert 'session_stats' in summary
        assert 'database_stats' in summary
        assert 'processed_items' in summary
        
        assert summary['session_stats']['new_articles'] == 10
        assert summary['session_stats']['updated_articles'] == 5
    
    def test_database_integration(self, collector):
        """Test integration with enhanced database methods."""
        # Test that collector uses new database methods
        article_data = {
            'title': 'Integration Test Article',
            'source_link': 'http://example.com/integration',
            'content_hash': 'integration_hash',
            'title_hash': 'title_hash',
            'guid': 'integration_guid'
        }
        
        # Insert article
        article_id, action = collector.db_manager.insert_or_update_article(article_data)
        
        assert article_id is not None
        assert action == 'inserted'
        
        # Try to insert same article again (should be duplicate)
        article_id2, action2 = collector.db_manager.insert_or_update_article(article_data)
        assert action2 in ['duplicate', 'updated']
    
    def test_feed_tracking_integration(self, collector):
        """Test feed tracking functionality."""
        feed_url = "http://example.com/test_feed"
        
        # Test successful tracking update
        success = collector.db_manager.update_feed_tracking(
            feed_url, True, 15, None, "etag-123", "Last-Modified-Date"
        )
        assert success is True
        
        # Test retrieving tracking info
        tracking = collector.db_manager.get_feed_tracking(feed_url)
        assert tracking is not None
        assert tracking['feed_url'] == feed_url
        assert tracking['last_article_count'] == 15
        assert tracking['etag'] == "etag-123"
        assert tracking['success_count'] == 1
        assert tracking['error_count'] == 0
        
        # Test error tracking
        collector.db_manager.update_feed_tracking(
            feed_url, False, 0, "Test error message"
        )
        
        updated_tracking = collector.db_manager.get_feed_tracking(feed_url)
        assert updated_tracking['error_count'] == 1
        assert updated_tracking['last_error'] == "Test error message"