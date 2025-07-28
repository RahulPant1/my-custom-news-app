"""Tests for RSS validator module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rss_validator import RSSValidator


class TestRSSValidator:
    
    @pytest.fixture
    def validator(self):
        """Create RSS validator instance."""
        return RSSValidator(timeout=5)
    
    @patch('rss_validator.requests.Session')
    @patch('rss_validator.feedparser')
    @patch('rss_validator.ET')
    def test_validate_single_feed_success(self, mock_et, mock_feedparser, mock_session_class, validator):
        """Test successful RSS feed validation."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.content = b'<rss><channel><title>Test Feed</title></channel></rss>'
        mock_response.raise_for_status.return_value = None
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value.get = mock_session.get
        
        # Mock XML parsing
        mock_et.fromstring.return_value = Mock()
        
        # Mock feedparser
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed.title = "Test Feed"
        mock_feed.feed.description = "Test Description"
        
        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article1"
        mock_entry.published = "2024-01-01"
        mock_entry.summary = "Test summary"
        
        mock_feed.entries = [mock_entry]
        mock_feedparser.parse.return_value = mock_feed
        
        result = validator.validate_single_feed("https://example.com/feed")
        
        assert result['valid'] is True
        assert result['accessible'] is True
        assert result['has_items'] is True
        assert result['item_count'] == 1
        assert result['title'] == "Test Feed"
        assert result['description'] == "Test Description"
        assert len(result['sample_articles']) == 1
        assert result['sample_articles'][0]['title'] == "Test Article"
    
    @patch('rss_validator.requests.Session')
    def test_validate_single_feed_network_error(self, mock_session_class, validator):
        """Test RSS feed validation with network error."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("Connection failed")
        mock_session_class.return_value.get = mock_session.get
        
        result = validator.validate_single_feed("https://example.com/feed")
        
        assert result['valid'] is False
        assert result['accessible'] is False
        assert "Network error" in result['error']
    
    @patch('rss_validator.requests.Session')
    @patch('rss_validator.ET')
    def test_validate_single_feed_invalid_xml(self, mock_et, mock_session_class, validator):
        """Test RSS feed validation with invalid XML."""
        # Mock HTTP response with invalid XML
        mock_response = Mock()
        mock_response.content = b'<invalid xml content'
        mock_response.raise_for_status.return_value = None
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value.get = mock_session.get
        
        # Mock XML parsing error
        from xml.etree.ElementTree import ParseError
        mock_et.fromstring.side_effect = ParseError("Invalid XML")
        
        result = validator.validate_single_feed("https://example.com/feed")
        
        assert result['valid'] is False
        assert result['accessible'] is True
        assert "Invalid XML format" in result['error']
    
    @patch('rss_validator.requests.Session')
    @patch('rss_validator.feedparser')
    @patch('rss_validator.ET')
    def test_validate_single_feed_bozo(self, mock_et, mock_feedparser, mock_session_class, validator):
        """Test RSS feed validation with feedparser bozo flag."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.content = b'<rss>content</rss>'
        mock_response.raise_for_status.return_value = None
        
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value.get = mock_session.get
        
        # Mock XML parsing success
        mock_et.fromstring.return_value = Mock()
        
        # Mock feedparser with bozo flag
        mock_feed = Mock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = Exception("Feed parsing error")
        
        mock_feedparser.parse.return_value = mock_feed
        
        result = validator.validate_single_feed("https://example.com/feed")
        
        assert result['valid'] is False
        assert result['accessible'] is True
        assert "Feed parsing error" in result['error']
    
    def test_validate_single_feed_invalid_url(self, validator):
        """Test RSS feed validation with invalid URL."""
        result = validator.validate_single_feed("not-a-valid-url")
        
        assert result['valid'] is False
        assert result['accessible'] is False
        assert "Invalid URL format" in result['error']
    
    @patch.object(RSSValidator, 'validate_single_feed')
    def test_validate_all_feeds(self, mock_validate_single, validator):
        """Test validation of all configured RSS feeds."""
        # Mock validation results
        def mock_validate(url):
            if "good" in url:
                return {
                    'url': url,
                    'valid': True,
                    'accessible': True,
                    'has_items': True,
                    'item_count': 5,
                    'error': None
                }
            else:
                return {
                    'url': url,
                    'valid': False,
                    'accessible': False,
                    'has_items': False,
                    'item_count': 0,
                    'error': 'Connection failed'
                }
        
        mock_validate_single.side_effect = mock_validate
        
        # Mock RSS_FEEDS for testing
        with patch('rss_validator.RSS_FEEDS', {
            'Technology': ['https://good.com/feed', 'https://bad.com/feed'],
            'Science': ['https://good-science.com/feed']
        }):
            results = validator.validate_all_feeds()
        
        assert len(results) == 2  # Two categories
        assert 'Technology' in results
        assert 'Science' in results
        assert len(results['Technology']) == 2
        assert len(results['Science']) == 1
    
    def test_get_validation_summary(self, validator):
        """Test validation summary generation."""
        mock_results = {
            'Technology': [
                {'valid': True, 'accessible': True, 'has_items': True, 'item_count': 10, 'url': 'url1', 'error': None},
                {'valid': False, 'accessible': False, 'has_items': False, 'item_count': 0, 'url': 'url2', 'error': 'Failed'}
            ],
            'Science': [
                {'valid': True, 'accessible': True, 'has_items': True, 'item_count': 5, 'url': 'url3', 'error': None}
            ]
        }
        
        summary = validator.get_validation_summary(mock_results)
        
        assert summary['total_feeds'] == 3
        assert summary['valid_feeds'] == 2
        assert summary['accessible_feeds'] == 2
        assert summary['feeds_with_items'] == 2
        assert summary['total_articles'] == 15  # 10 + 5
        
        # Check category stats
        assert summary['category_stats']['Technology']['valid'] == 1
        assert summary['category_stats']['Technology']['total'] == 2
        assert summary['category_stats']['Science']['valid'] == 1
        assert summary['category_stats']['Science']['total'] == 1
        
        # Check problematic feeds
        assert len(summary['problematic_feeds']) == 1
        assert summary['problematic_feeds'][0]['url'] == 'url2'
        assert summary['problematic_feeds'][0]['category'] == 'Technology'
    
    @patch('builtins.print')
    def test_print_validation_report(self, mock_print, validator):
        """Test validation report printing."""
        mock_results = {
            'Technology': [
                {'valid': True, 'accessible': True, 'has_items': True, 'item_count': 10, 'url': 'url1', 'error': None},
            ],
            'Science': [
                {'valid': False, 'accessible': False, 'has_items': False, 'item_count': 0, 'url': 'url2', 'error': 'Connection failed'}
            ]
        }
        
        validator.print_validation_report(mock_results)
        
        # Verify that print was called (report was generated)
        assert mock_print.called
        
        # Check some expected content in the printed output
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        report_content = '\n'.join(print_calls)
        
        assert "RSS FEED VALIDATION REPORT" in report_content
        assert "Total feeds checked: 2" in report_content
        assert "PROBLEMATIC FEEDS" in report_content
    
    @patch.object(RSSValidator, 'validate_all_feeds')
    @patch.object(RSSValidator, 'print_validation_report')
    def test_run_feed_validation(self, mock_print_report, mock_validate_all):
        """Test the run_feed_validation function."""
        from rss_validator import run_feed_validation
        
        mock_results = {'Technology': [{'valid': True}]}
        mock_validate_all.return_value = mock_results
        
        result = run_feed_validation()
        
        # Verify the function calls the right methods
        mock_validate_all.assert_called_once()
        mock_print_report.assert_called_once_with(mock_results)
        
        # Should return the validation results
        assert result == mock_results