"""Tests for database operations."""

import pytest
import tempfile
import os
import json
from datetime import datetime

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import DatabaseManager


class TestDatabaseManager:
    
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
    
    def test_database_initialization(self, temp_db):
        """Test database initialization."""
        # Check that the database file was created
        assert os.path.exists(temp_db.db_path)

        # Check that tables were created
        import sqlite3
        conn = sqlite3.connect(temp_db.db_path)
        cursor = conn.cursor()
        
        # Check articles table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
        assert cursor.fetchone() is not None
        
        # Check user_preferences table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
        assert cursor.fetchone() is not None
        
        conn.close()
    
    def test_insert_article(self, temp_db):
        """Test article insertion."""
        article_data = {
            'title': 'Test Article',
            'author': 'Test Author',
            'publication_date': '2024-01-01T10:00:00',
            'source_link': 'https://example.com/article1',
            'original_summary': 'This is a test article summary.',
            'rss_category': 'Technology',
            'ai_categories': ['Technology & Gadgets'],
            'ai_summary': 'AI generated summary',
            'trending_flag': True,
            'content_hash': 'test_hash_123'
        }
        
        article_id = temp_db.insert_article(article_data)
        assert article_id is not None
        assert article_id > 0
        
        # Test duplicate insertion (should return None)
        duplicate_id = temp_db.insert_article(article_data)
        assert duplicate_id is None
    
    def test_get_articles_by_categories(self, temp_db):
        """Test article retrieval by categories."""
        # Insert test articles
        articles = [
            {
                'title': 'Tech Article 1',
                'source_link': 'https://example.com/tech1',
                'original_summary': 'Tech summary',
                'ai_categories': ['Technology & Gadgets'],
                'content_hash': 'hash1'
            },
            {
                'title': 'Science Article 1',
                'source_link': 'https://example.com/science1',
                'original_summary': 'Science summary',
                'ai_categories': ['Science & Discovery'],
                'content_hash': 'hash2'
            },
            {
                'title': 'Mixed Article',
                'source_link': 'https://example.com/mixed1',
                'original_summary': 'Mixed summary',
                'ai_categories': ['Technology & Gadgets', 'Science & Discovery'],
                'content_hash': 'hash3'
            }
        ]
        
        for article in articles:
            temp_db.insert_article(article)
        
        # Test retrieval by single category
        tech_articles = temp_db.get_articles_by_categories(['Technology & Gadgets'])
        assert len(tech_articles) == 2  # Tech Article 1 and Mixed Article
        
        # Test retrieval by multiple categories
        science_articles = temp_db.get_articles_by_categories(['Science & Discovery'])
        assert len(science_articles) == 2  # Science Article 1 and Mixed Article
        
        # Test limit
        limited_articles = temp_db.get_articles_by_categories(['Technology & Gadgets'], limit=1)
        assert len(limited_articles) == 1
    
    def test_user_preferences(self, temp_db):
        """Test user preferences operations."""
        user_data = {
            'user_id': 'test_user_123',
            'email': 'test@example.com',
            'selected_categories': ['Technology & Gadgets', 'Science & Discovery'],
            'digest_frequency': 'daily',
            'articles_per_digest': 15,
            'preferred_output_format': 'markdown',
            'feedback_history': {'1': {'feedback': 'like', 'timestamp': '2024-01-01T10:00:00'}}
        }
        
        # Test insert
        success = temp_db.insert_or_update_user_preferences(user_data)
        assert success is True
        
        # Test retrieval
        retrieved = temp_db.get_user_preferences('test_user_123')
        assert retrieved is not None
        assert retrieved['user_id'] == 'test_user_123'
        assert retrieved['email'] == 'test@example.com'
        assert retrieved['selected_categories'] == ['Technology & Gadgets', 'Science & Discovery']
        assert retrieved['articles_per_digest'] == 15
        
        # Test update
        user_data['articles_per_digest'] = 20
        success = temp_db.insert_or_update_user_preferences(user_data)
        assert success is True
        
        # Verify update
        updated = temp_db.get_user_preferences('test_user_123')
        assert updated['articles_per_digest'] == 20
        
        # Test non-existent user
        none_user = temp_db.get_user_preferences('nonexistent_user')
        assert none_user is None
    
    def test_article_count(self, temp_db):
        """Test article count functionality."""
        # Initially should be 0
        assert temp_db.get_article_count() == 0
        
        # Insert some articles
        for i in range(5):
            article_data = {
                'title': f'Test Article {i}',
                'source_link': f'https://example.com/article{i}',
                'content_hash': f'hash_{i}'
            }
            temp_db.insert_article(article_data)
        
        assert temp_db.get_article_count() == 5
    
    def test_cleanup_old_articles(self, temp_db):
        """Test cleanup of old articles."""
        # This is a basic test - in reality, we'd need to manipulate dates
        # For now, just test that the method runs without error
        deleted_count = temp_db.cleanup_old_articles(30)
        assert isinstance(deleted_count, int)
        assert deleted_count >= 0
    
    def test_json_serialization(self, temp_db):
        """Test that JSON fields are properly handled."""
        article_data = {
            'title': 'JSON Test Article',
            'source_link': 'https://example.com/json_test',
            'ai_categories': ['Technology & Gadgets', 'Science & Discovery'],  # List
            'content_hash': 'json_hash'
        }
        
        article_id = temp_db.insert_article(article_data)
        assert article_id is not None
        
        # Retrieve and verify JSON deserialization
        articles = temp_db.get_articles_by_categories(['Technology & Gadgets'])
        assert len(articles) > 0
        
        retrieved_article = next(a for a in articles if a['id'] == article_id)
        assert isinstance(retrieved_article['ai_categories'], list)
        assert retrieved_article['ai_categories'] == ['Technology & Gadgets', 'Science & Discovery']