"""Tests for interactive interface."""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import DatabaseManager

# Only import interactive interface if Flask is available
try:
    from interactive_interface import InteractiveNewsInterface
    flask_available = True
except ImportError:
    flask_available = False


@pytest.mark.skipif(not flask_available, reason="Flask not available")
class TestInteractiveNewsInterface:
    """Test interactive news interface."""
    
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
    def interface(self, temp_db):
        """Create interactive interface with temporary database."""
        with patch('interactive_interface.DatabaseManager') as mock_db_class:
            mock_db_class.return_value = temp_db
            
            interface = InteractiveNewsInterface(port=5001, debug=False)
            interface.db_manager = temp_db
            interface.create_templates()  # Create templates for testing
            return interface
    
    @pytest.fixture
    def client(self, interface):
        """Create Flask test client."""
        interface.app.config['TESTING'] = True
        return interface.app.test_client()
    
    def test_interface_initialization(self, interface):
        """Test interface initialization."""
        assert interface.port == 5001
        assert interface.debug is False
        assert interface.app is not None
        assert interface.category_info is not None
        assert len(interface.category_info) == 10  # All AI categories
    
    def test_category_info_structure(self, interface):
        """Test category info structure."""
        for category, info in interface.category_info.items():
            assert 'description' in info
            assert 'icon' in info
            assert 'sample_headlines' in info
            assert 'color' in info
            assert isinstance(info['sample_headlines'], list)
            assert len(info['sample_headlines']) >= 3
    
    def test_index_route(self, client, temp_db):
        """Test index route."""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'News Digest' in response.data
        assert b'Dashboard' in response.data
    
    def test_categories_route(self, client):
        """Test categories route."""
        response = client.get('/categories')
        
        assert response.status_code == 200
        assert b'Categories' in response.data
        assert b'Technology & Gadgets' in response.data
        assert b'Science & Discovery' in response.data
    
    def test_create_user_get(self, client):
        """Test create user GET request."""
        response = client.get('/create-user')
        
        assert response.status_code == 200
        assert b'Create User' in response.data
        assert b'Select Categories' in response.data
    
    def test_create_user_post_success(self, client, temp_db):
        """Test successful user creation."""
        data = {
            'user_id': 'test_user_123',
            'email': 'test@example.com',
            'categories': ['Technology & Gadgets', 'Science & Discovery'],
            'articles_per_digest': 15,
            'output_format': 'markdown'
        }
        
        response = client.post('/create-user', data=data, follow_redirects=True)
        
        assert response.status_code == 200
        # Should redirect to user profile
        assert b'test_user_123' in response.data
    
    def test_create_user_post_no_categories(self, client):
        """Test user creation without categories."""
        data = {
            'user_id': 'test_user',
            'email': 'test@example.com',
            'articles_per_digest': 10,
            'output_format': 'text'
            # No categories selected
        }
        
        response = client.post('/create-user', data=data)
        
        assert response.status_code == 200
        assert b'Please select at least one category' in response.data
    
    def test_user_profile_existing(self, client, temp_db):
        """Test user profile for existing user."""
        # Create a user first
        from user_interface import UserPreferencesManager
        prefs_manager = UserPreferencesManager(temp_db)
        user_id = prefs_manager.create_user(
            user_id='profile_test_user',
            categories=['Technology & Gadgets'],
            articles_per_digest=10
        )
        
        response = client.get(f'/user/{user_id}')
        
        assert response.status_code == 200
        assert user_id.encode() in response.data
        assert b'Technology & Gadgets' in response.data
    
    def test_user_profile_nonexistent(self, client):
        """Test user profile for non-existent user."""
        response = client.get('/user/nonexistent_user', follow_redirects=True)
        
        assert response.status_code == 200
        assert b'not found' in response.data
    
    def test_edit_user_get(self, client, temp_db):
        """Test edit user GET request."""
        # Create a user first
        from user_interface import UserPreferencesManager
        prefs_manager = UserPreferencesManager(temp_db)
        user_id = prefs_manager.create_user(
            user_id='edit_test_user',
            categories=['Science & Discovery'],
            preferred_output_format='text'
        )
        
        response = client.get(f'/user/{user_id}/edit')
        
        assert response.status_code == 200
        assert b'Edit' in response.data
        assert user_id.encode() in response.data
    
    def test_edit_user_post_success(self, client, temp_db):
        """Test successful user editing."""
        # Create a user first
        from user_interface import UserPreferencesManager
        prefs_manager = UserPreferencesManager(temp_db)
        user_id = prefs_manager.create_user(
            user_id='edit_success_user',
            categories=['Science & Discovery']
        )
        
        data = {
            'email': 'updated@example.com',
            'categories': ['Technology & Gadgets', 'Health & Wellness'],
            'articles_per_digest': 20,
            'output_format': 'email'
        }
        
        response = client.post(f'/user/{user_id}/edit', data=data, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'updated successfully' in response.data
    
    def test_generate_digest(self, client, temp_db):
        """Test digest generation."""
        # Create user and add some articles
        from user_interface import UserPreferencesManager
        prefs_manager = UserPreferencesManager(temp_db)
        user_id = prefs_manager.create_user(
            user_id='digest_test_user',
            categories=['Technology & Gadgets']
        )
        
        # Add a test article
        temp_db.insert_article({
            'title': 'Test Tech Article',
            'source_link': 'http://example.com/tech1',
            'ai_categories': ['Technology & Gadgets'],
            'ai_summary': 'This is a test technology article.',
            'content_hash': 'digest_test_hash'
        })
        
        response = client.get(f'/generate-digest/{user_id}')
        
        assert response.status_code == 200
        assert b'Digest' in response.data
    
    def test_api_stats(self, client, temp_db):
        """Test stats API endpoint."""
        response = client.get('/api/stats')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'total_articles' in data
        assert isinstance(data['total_articles'], int)
    
    def test_api_users(self, client, temp_db):
        """Test users API endpoint."""
        # Create a test user
        from user_interface import UserPreferencesManager
        prefs_manager = UserPreferencesManager(temp_db)
        user_id = prefs_manager.create_user(
            user_id='api_test_user',
            email='api@example.com',
            categories=['Science & Discovery']
        )
        
        response = client.get('/api/users')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'users' in data
        assert len(data['users']) >= 1
        
        # Find our test user
        test_user = next((u for u in data['users'] if u['user_id'] == user_id), None)
        assert test_user is not None
        assert test_user['email'] == 'api@example.com'
        assert 'Science & Discovery' in test_user['categories']
    
    def test_api_category_preview(self, client, temp_db):
        """Test category preview API endpoint."""
        # Add test article for the category
        temp_db.insert_article({
            'title': 'Test Science Article',
            'source_link': 'http://example.com/science1',
            'ai_categories': ['Science & Discovery'],
            'ai_summary': 'This is a test science article summary.',
            'original_summary': 'Original science content',
            'publication_date': '2024-01-15T10:00:00',
            'trending_flag': True,
            'content_hash': 'preview_test_hash'
        })
        
        response = client.get('/api/category-preview/Science%20%26%20Discovery')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['category'] == 'Science & Discovery'
        assert 'info' in data
        assert 'recent_articles' in data
        assert 'feed_count' in data
        
        if data['recent_articles']:
            article = data['recent_articles'][0]
            assert 'title' in article
            assert 'summary' in article
            assert 'trending' in article
    
    def test_api_category_preview_invalid(self, client):
        """Test category preview with invalid category."""
        response = client.get('/api/category-preview/Invalid%20Category')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_add_feedback(self, client, temp_db):
        """Test adding user feedback."""
        # Create user and article
        from user_interface import UserPreferencesManager
        prefs_manager = UserPreferencesManager(temp_db)
        user_id = prefs_manager.create_user(
            user_id='feedback_test_user',
            categories=['Technology & Gadgets']
        )
        
        article_id = temp_db.insert_article({
            'title': 'Feedback Test Article',
            'source_link': 'http://example.com/feedback1',
            'ai_categories': ['Technology & Gadgets'],
            'content_hash': 'feedback_test_hash'
        })
        
        response = client.get(f'/feedback/{user_id}/{article_id}/like', follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Feedback recorded' in response.data
        
        # Verify feedback was stored
        prefs = prefs_manager.get_user_preferences(user_id)
        assert str(article_id) in prefs['feedback_history']
        assert prefs['feedback_history'][str(article_id)]['feedback'] == 'like'
    
    def test_add_invalid_feedback(self, client, temp_db):
        """Test adding invalid feedback."""
        from user_interface import UserPreferencesManager
        prefs_manager = UserPreferencesManager(temp_db)
        user_id = prefs_manager.create_user(
            user_id='invalid_feedback_user',
            categories=['Technology & Gadgets']
        )
        
        response = client.get(f'/feedback/{user_id}/123/invalid', follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Invalid feedback' in response.data
    
    def test_sample_headline_quality(self, interface):
        """Test quality of sample headlines."""
        for category, info in interface.category_info.items():
            headlines = info['sample_headlines']
            
            # Check headline length (should be realistic)
            for headline in headlines:
                assert 20 <= len(headline) <= 120, f"Headline length issue in {category}: {headline}"
            
            # Check for variety (headlines shouldn't be too similar)
            first_words = [h.split()[0].lower() for h in headlines if h]
            unique_first_words = set(first_words)
            
            # At least 2 different first words for variety
            assert len(unique_first_words) >= 2, f"Headlines too similar in {category}"
