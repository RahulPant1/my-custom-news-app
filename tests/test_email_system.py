"""Integration tests for the refactored email system."""

import unittest
import tempfile
import os
import json
from datetime import datetime
from unittest.mock import Mock, patch

# Add src to path for testing
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from src.settings.email_config import validate_email_setup
except ImportError:
    # Fallback if email_config module doesn't exist
    def validate_email_setup():
        return {'valid': False, 'errors': ['Email configuration not found']}

try:
    from src.repositories.email_repository import EmailRepository
except ImportError:
    # Fallback if repository doesn't exist
    EmailRepository = None

try:
    from src.services.email_service import EmailDeliveryService
except ImportError:
    # Fallback if service doesn't exist
    EmailDeliveryService = None

try:
    from src.templates.email_templates import render_email_template
except ImportError:
    # Fallback if templates don't exist
    def render_email_template(*args, **kwargs):
        return "<html><body>Test email</body></html>"

try:
    from src.email_delivery_refactored import RefactoredEmailDeliveryManager
except ImportError:
    # Import from main src directory
    from email_delivery_refactored import RefactoredEmailDeliveryManager


class TestEmailConfiguration(unittest.TestCase):
    """Test email configuration management."""
    
    def test_smtp_config_validation(self):
        """Test SMTP configuration validation."""
        # Test email configuration validation from environment
        with patch.dict(os.environ, {
            'SMTP_SERVER': 'smtp.gmail.com',
            'SMTP_PORT': '587',
            'SMTP_USERNAME': 'test@example.com',
            'SMTP_PASSWORD': 'password',
            'FROM_EMAIL': 'test@example.com',
            'FROM_NAME': 'Test'
        }):
            status = validate_email_setup()
            self.assertIsInstance(status, dict)
            self.assertIn('valid', status)
        
        # Test invalid port
        with patch.dict(os.environ, {
            'SMTP_PORT': '99999'
        }):
            status = validate_email_setup()
            # Should handle invalid port gracefully
            self.assertIsInstance(status, dict)
        
        # Test invalid email
        with patch.dict(os.environ, {
            'SMTP_USERNAME': 'invalid-email',
            'FROM_EMAIL': 'invalid-email'
        }):
            status = validate_email_setup()
            # Should handle invalid email gracefully
            self.assertIsInstance(status, dict)
    
    @patch.dict(os.environ, {
        'SMTP_USERNAME': 'test@example.com',
        'SMTP_PASSWORD': 'test-password'
    })
    def test_configuration_validation(self):
        """Test configuration validation with environment variables."""
        status = validate_email_setup()
        self.assertTrue(status['valid'])
        self.assertEqual(status['smtp_server'], 'smtp.gmail.com')
    
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_required_config(self):
        """Test validation with missing required configuration."""
        status = validate_email_setup()
        self.assertFalse(status['valid'])
        self.assertTrue(len(status['errors']) > 0)


class TestEmailRepository(unittest.TestCase):
    """Test email repository operations."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        
        # Initialize database schema
        from database import DatabaseManager
        db_manager = DatabaseManager(self.temp_db.name)
        
        self.repo = EmailRepository(self.temp_db.name)
    
    def tearDown(self):
        """Clean up test database."""
        os.unlink(self.temp_db.name)
    
    def test_email_preferences_crud(self):
        """Test email preferences CRUD operations."""
        # Create preferences
        prefs = EmailPreferences(
            user_id="test_user",
            email_enabled=True,
            delivery_frequency="weekly",
            include_feedback_links=False
        )
        
        success = self.repo.save_email_preferences(prefs)
        self.assertTrue(success)
        
        # Read preferences
        retrieved = self.repo.get_email_preferences("test_user")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.user_id, "test_user")
        self.assertEqual(retrieved.delivery_frequency, "weekly")
        self.assertFalse(retrieved.include_feedback_links)
        
        # Update preferences
        prefs.email_enabled = False
        success = self.repo.save_email_preferences(prefs)
        self.assertTrue(success)
        
        updated = self.repo.get_email_preferences("test_user")
        self.assertFalse(updated.email_enabled)
    
    def test_feedback_recording(self):
        """Test feedback recording."""
        feedback = FeedbackRecord(
            id=None,
            user_id="test_user",
            article_id=123,
            email_delivery_id=None,
            feedback_type="like",
            feedback_source="email"
        )
        
        success = self.repo.record_feedback(feedback)
        self.assertTrue(success)
        
        # Test engagement metrics update
        success = self.repo.update_engagement_metrics("test_user", "like")
        self.assertTrue(success)
        
        # Get engagement summary
        summary = self.repo.get_user_engagement_summary("test_user")
        self.assertGreaterEqual(summary.get('total_likes', 0), 0)


class TestEmailTemplates(unittest.TestCase):
    """Test email template system."""
    
    def test_news_digest_template_rendering(self):
        """Test news digest template rendering."""
        template_data = {
            'user_id': 'test_user',
            'categories': {
                'Technology': [{
                    'id': 1,
                    'title': 'Test Article',
                    'ai_summary': 'This is a test article summary.',
                    'source_link': 'https://example.com/article',
                    'author': 'Test Author',
                    'publication_date': datetime.now().isoformat()
                }]
            },
            'user_prefs': {'user_id': 'test_user', 'email': 'test@example.com'},
            'email_prefs': {
                'include_feedback_links': True,
                'include_social_sharing': True
            },
            'highlights': {
                'one_liner': 'Test insight of the day'
            },
            'base_url': 'http://localhost:5000',
            'unsubscribe_url': 'http://localhost:5000/unsubscribe?user_id=test_user'
        }
        
        html = render_email_template('news_digest', template_data)
        
        # Verify key elements are present
        self.assertIn('Test Article', html)
        self.assertIn('test_user', html)
        self.assertIn('Test insight of the day', html)
        self.assertIn('👍 Like', html)
        self.assertIn('🐦', html)  # Twitter share button
        self.assertIn('unsubscribe', html)
    
    def test_template_validation(self):
        """Test template data validation."""
        from templates.email_templates import template_manager
        
        # Missing required fields
        incomplete_data = {'user_id': 'test_user'}
        
        missing_fields = template_manager.validate_template_data('news_digest', incomplete_data)
        self.assertTrue(len(missing_fields) > 0)
        self.assertIn('categories', missing_fields)


class TestEmailService(unittest.TestCase):
    """Test email service with mocked dependencies."""
    
    def setUp(self):
        """Set up test service with mocks."""
        self.mock_email_repo = Mock()
        self.mock_user_repo = Mock()
        self.mock_ai_service = Mock()
        
        # Create test config
        smtp_config = SMTPConfig(
            server="smtp.test.com",
            port=587,
            username="test@example.com",
            password="password",
            from_email="test@example.com",
            from_name="Test Service"
        )
        
        self.config = EmailServiceConfig(
            smtp=smtp_config,
            base_url="http://localhost:5000"
        )
        
        self.service = EmailDeliveryService(
            email_repo=self.mock_email_repo,
            user_repo=self.mock_user_repo,
            config=self.config,
            ai_service=self.mock_ai_service
        )
    
    def test_email_delivery_validation(self):
        """Test email delivery validation."""
        # Mock user not found
        self.mock_user_repo.get_user_preferences.return_value = None
        
        success, message = self.service.send_digest_email('nonexistent_user', {})
        self.assertFalse(success)
        self.assertIn('not found', message)
        
        # Mock user without email
        self.mock_user_repo.get_user_preferences.return_value = {'user_id': 'test_user'}
        
        success, message = self.service.send_digest_email('test_user', {})
        self.assertFalse(success)
        self.assertIn('No email address', message)
    
    def test_preferences_management(self):
        """Test email preferences management."""
        # Mock existing preferences
        mock_prefs = EmailPreferences(
            user_id="test_user",
            email_enabled=True,
            delivery_frequency="daily"
        )
        self.mock_email_repo.get_email_preferences.return_value = mock_prefs
        self.mock_email_repo.save_email_preferences.return_value = True
        
        # Update preferences
        success = self.service.update_email_preferences("test_user", {
            'delivery_frequency': 'weekly',
            'email_enabled': False
        })
        
        self.assertTrue(success)
        self.mock_email_repo.save_email_preferences.assert_called_once()
    
    @patch('services.email_service.smtplib.SMTP')
    def test_smtp_email_sending(self, mock_smtp):
        """Test SMTP email sending with mocked SMTP."""
        # Mock SMTP server
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        success, message = self.service._send_smtp_email(
            "test@example.com", 
            "Test Subject", 
            "<html><body>Test</body></html>"
        )
        
        self.assertTrue(success)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()


class TestRefactoredEmailManager(unittest.TestCase):
    """Test the refactored email delivery manager."""
    
    @patch('email_delivery_refactored.validate_email_setup')
    @patch('email_delivery_refactored.get_email_config')
    def test_initialization_with_valid_config(self, mock_get_config, mock_validate):
        """Test initialization with valid configuration."""
        # Mock successful configuration
        mock_validate.return_value = {'valid': True}
        
        smtp_config = SMTPConfig(
            server="smtp.test.com",
            port=587,
            username="test@example.com",
            password="password",
            from_email="test@example.com",
            from_name="Test"
        )
        
        mock_get_config.return_value = EmailServiceConfig(
            smtp=smtp_config,
            base_url="http://localhost:5000"
        )
        
        # Mock database manager
        mock_db_manager = Mock()
        mock_db_manager.db_path = ":memory:"
        
        manager = RefactoredEmailDeliveryManager(mock_db_manager)
        self.assertTrue(manager.is_configured())
    
    @patch('email_delivery_refactored.validate_email_setup')
    def test_initialization_with_invalid_config(self, mock_validate):
        """Test initialization with invalid configuration."""
        mock_validate.return_value = {
            'valid': False,
            'errors': ['Missing SMTP credentials']
        }
        
        mock_db_manager = Mock()
        manager = RefactoredEmailDeliveryManager(mock_db_manager)
        self.assertFalse(manager.is_configured())
    
    def test_configuration_status(self):
        """Test configuration status reporting."""
        with patch('email_delivery_refactored.validate_email_setup') as mock_validate:
            mock_validate.return_value = {
                'valid': False,
                'errors': ['Test error'],
                'smtp_server': 'smtp.gmail.com'
            }
            
            mock_db_manager = Mock()
            manager = RefactoredEmailDeliveryManager(mock_db_manager)
            
            status = manager.get_configuration_status()
            self.assertFalse(status['configured'])
            self.assertFalse(status['config_valid'])
            self.assertIn('Test error', status['errors'])


if __name__ == '__main__':
    # Set up test environment variables
    os.environ.update({
        'SMTP_USERNAME': 'test@example.com',
        'SMTP_PASSWORD': 'test-password',
        'BASE_URL': 'http://localhost:5000'
    })
    
    unittest.main()