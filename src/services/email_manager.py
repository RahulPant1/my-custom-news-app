"""Unified Email Manager - Single interface for all email operations."""

from typing import Dict, List, Optional, Tuple
import logging

from src.services.unified_email_service import UnifiedEmailService, UnifiedEmailServiceFactory
from src.repositories.email_repository import EmailDelivery, EmailPreferences
from src.settings.email_config import get_email_config, validate_email_setup
from src.database import DatabaseManager
from src.ai_adapters import AIServiceManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseUserAdapter:
    """Adapter to make DatabaseManager compatible with UserRepository protocol."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Get user preferences."""
        return self.db_manager.get_user_preferences(user_id)
    
    def update_user_email(self, user_id: str, email: str) -> bool:
        """Update user email address."""
        try:
            return self.db_manager.update_user_email(user_id, email)
        except AttributeError:
            logger.warning("DatabaseManager does not support update_user_email method")
            return False


class AIServiceAdapter:
    """Adapter to make AIServiceManager compatible with AIService protocol."""
    
    def __init__(self, ai_manager: AIServiceManager):
        self.ai_manager = ai_manager
    
    def generate_summary(self, title: str, content: str) -> Dict:
        """Generate AI summary."""
        try:
            response = self.ai_manager.generate_summary(title, content)
            return {
                'success': response.success if hasattr(response, 'success') else True,
                'content': response.content if hasattr(response, 'content') else response,
                'provider': response.provider if hasattr(response, 'provider') else 'unknown',
                'error': response.error if hasattr(response, 'error') else None
            }
        except Exception as e:
            return {
                'success': False,
                'content': None,
                'provider': None,
                'error': str(e)
            }


class EmailManager:
    """Unified email manager providing a single interface for all email operations."""
    
    def __init__(self, db_manager: DatabaseManager = None, ai_manager: AIServiceManager = None):
        self.db_manager = db_manager or DatabaseManager()
        self.ai_manager = ai_manager
        self._email_service = None
        self._config = None
        self._init_error = None
        
        # Initialize the service
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize the email service with proper error handling."""
        try:
            # Validate email configuration
            config_status = validate_email_setup()
            if not config_status['valid']:
                error_msg = f"Email configuration invalid: {config_status['errors']}"
                logger.warning("Email service not initialized", extra={
                    'errors': config_status['errors']
                })
                self._init_error = error_msg
                return
            
            # Get configuration
            self._config = get_email_config()
            
            # Create adapters
            user_repo = DatabaseUserAdapter(self.db_manager)
            ai_service = AIServiceAdapter(self.ai_manager) if self.ai_manager else None
            
            # Create unified email service
            self._email_service = UnifiedEmailServiceFactory.create_email_service(
                db_path=self.db_manager.db_path,
                user_repo=user_repo,
                config=self._config,
                ai_service=ai_service
            )
            
            logger.info("Email manager initialized successfully", extra={
                'ai_service_available': ai_service is not None,
                'config_valid': True
            })
            
        except Exception as e:
            error_msg = f"Failed to initialize email service: {e}"
            logger.error("Email manager initialization failed", extra={
                'error': str(e)
            }, exc_info=True)
            self._init_error = error_msg
    
    def is_configured(self) -> bool:
        """Check if email system is properly configured and ready."""
        return self._email_service is not None and self._init_error is None
    
    def get_configuration_status(self) -> Dict:
        """Get detailed configuration status."""
        if self._init_error:
            return {
                'configured': False,
                'error': self._init_error,
                'config_valid': False
            }
        
        config_status = validate_email_setup()
        
        return {
            'configured': self.is_configured(),
            'config_valid': config_status['valid'],
            'errors': config_status.get('errors', []),
            'smtp_server': config_status.get('smtp_server'),
            'smtp_port': config_status.get('smtp_port'),
            'from_email': config_status.get('from_email'),
            'base_url': config_status.get('base_url')
        }
    
    # Email delivery methods
    def send_digest_email(self, user_id: str, digest_data: Dict) -> Tuple[bool, str]:
        """Send digest email to user."""
        if not self.is_configured():
            return False, "Email system not configured. Check SMTP settings."
        
        try:
            return self._email_service.send_digest_email(user_id, digest_data)
        except Exception as e:
            error_msg = f"Email delivery failed: {str(e)}"
            logger.error("Email delivery exception", extra={
                'user_id': user_id,
                'error': str(e)
            }, exc_info=True)
            return False, error_msg
    
    def send_bulk_digest_emails(self, user_digest_pairs: List[Tuple[str, Dict]]) -> Dict:
        """Send digest emails to multiple users and return results."""
        results = {
            'total': len(user_digest_pairs),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        if not self.is_configured():
            error_msg = "Email system not configured"
            results['errors'].append(error_msg)
            results['failed'] = results['total']
            return results
        
        for user_id, digest_data in user_digest_pairs:
            try:
                success, message = self.send_digest_email(user_id, digest_data)
                if success:
                    results['successful'] += 1
                    logger.info("Bulk email sent", extra={
                        'user_id': user_id,
                        'success': True
                    })
                else:
                    results['failed'] += 1
                    results['errors'].append(f"{user_id}: {message}")
                    logger.warning("Bulk email failed", extra={
                        'user_id': user_id,
                        'error': message
                    })
            except Exception as e:
                results['failed'] += 1
                error_msg = f"{user_id}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error("Bulk email exception", extra={
                    'user_id': user_id,
                    'error': str(e)
                }, exc_info=True)
        
        logger.info("Bulk email delivery completed", extra={
            'total': results['total'],
            'successful': results['successful'],
            'failed': results['failed']
        })
        
        return results
    
    # User preference management
    def get_email_preferences(self, user_id: str) -> Optional[Dict]:
        """Get email preferences for a user."""
        if not self.is_configured():
            return None
        
        try:
            prefs = self._email_service.get_user_email_preferences(user_id)
            if not prefs:
                return None
            
            return {
                'user_id': prefs.user_id,
                'email_enabled': prefs.email_enabled,
                'delivery_frequency': prefs.delivery_frequency,
                'delivery_time': prefs.delivery_time,
                'delivery_timezone': prefs.delivery_timezone,
                'email_format': prefs.email_format,
                'include_feedback_links': prefs.include_feedback_links,
                'include_social_sharing': prefs.include_social_sharing,
                'personalized_subject': prefs.personalized_subject
            }
        except Exception as e:
            logger.error("Failed to get email preferences", extra={
                'user_id': user_id,
                'error': str(e)
            }, exc_info=True)
            return None
    
    def update_email_preferences(self, user_id: str, preferences: Dict) -> bool:
        """Update email preferences for a user."""
        if not self.is_configured():
            return False
        
        try:
            success = self._email_service.update_email_preferences(user_id, preferences)
            if success:
                logger.info("Email preferences updated", extra={
                    'user_id': user_id,
                    'preferences': preferences
                })
            else:
                logger.warning("Failed to update email preferences", extra={
                    'user_id': user_id
                })
            return success
        except Exception as e:
            logger.error("Email preference update exception", extra={
                'user_id': user_id,
                'error': str(e)
            }, exc_info=True)
            return False
    
    def enable_email_delivery(self, user_id: str) -> bool:
        """Enable email delivery for a user."""
        return self.update_email_preferences(user_id, {'email_enabled': True})
    
    def disable_email_delivery(self, user_id: str) -> bool:
        """Disable email delivery for a user."""
        return self.update_email_preferences(user_id, {'email_enabled': False})
    
    # Feedback and engagement methods
    def record_user_feedback(self, user_id: str, article_id: int, feedback_type: str,
                           email_delivery_id: int = None, share_platform: str = None) -> bool:
        """Record user feedback and update engagement metrics."""
        if not self.is_configured():
            return False
        
        try:
            success = self._email_service.record_user_feedback(
                user_id, article_id, feedback_type, email_delivery_id, share_platform
            )
            if success:
                logger.info("User feedback recorded", extra={
                    'user_id': user_id,
                    'article_id': article_id,
                    'feedback_type': feedback_type,
                    'share_platform': share_platform
                })
            return success
        except Exception as e:
            logger.error("Failed to record user feedback", extra={
                'user_id': user_id,
                'article_id': article_id,
                'feedback_type': feedback_type,
                'error': str(e)
            }, exc_info=True)
            return False
    
    def get_user_engagement_summary(self, user_id: str, days: int = 30) -> Dict:
        """Get engagement summary for a user."""
        if not self.is_configured():
            return {}
        
        try:
            return self._email_service.get_user_engagement_summary(user_id, days)
        except Exception as e:
            logger.error("Failed to get engagement summary", extra={
                'user_id': user_id,
                'days': days,
                'error': str(e)
            }, exc_info=True)
            return {}
    
    def get_delivery_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get delivery history for a user."""
        if not self.is_configured():
            return []
        
        try:
            deliveries = self._email_service.get_delivery_history(user_id, limit)
            
            # Convert to dict format for consistency
            return [{
                'id': delivery.id,
                'email_address': delivery.email_address,
                'subject_line': delivery.subject_line,
                'delivery_status': delivery.delivery_status,
                'sent_at': delivery.sent_at,
                'error_message': delivery.error_message,
                'created_at': delivery.created_at
            } for delivery in deliveries]
        except Exception as e:
            logger.error("Failed to get delivery history", extra={
                'user_id': user_id,
                'limit': limit,
                'error': str(e)
            }, exc_info=True)
            return []
    
    # Administrative methods
    def get_email_statistics(self) -> Dict:
        """Get email system statistics."""
        if not self.is_configured():
            return {'configured': False}
        
        try:
            # This would need to be implemented in the email service
            # For now, return basic info
            return {
                'configured': True,
                'service': 'unified_email_service',
                'ai_enabled': self.ai_manager is not None
            }
        except Exception as e:
            logger.error("Failed to get email statistics", extra={
                'error': str(e)
            }, exc_info=True)
            return {'configured': True, 'error': str(e)}
    
    def test_email_configuration(self, test_email: str = None) -> Tuple[bool, str]:
        """Test email configuration by sending a test email."""
        if not self.is_configured():
            return False, "Email system not configured"
        
        # Use a test email address or the configured from_email
        if not test_email:
            test_email = self._config.smtp.from_email
        
        # Create a simple test digest
        test_digest = {
            'categories': {
                'System Test': [{
                    'id': 0,
                    'title': 'Email Configuration Test',
                    'ai_summary': 'This is a test email to verify the email system configuration.',
                    'source_link': 'http://localhost:5000/test',
                    'author': 'System',
                    'publication_date': '2025-01-15T10:00:00Z'
                }]
            }
        }
        
        try:
            success, message = self.send_digest_email('test_user', test_digest)
            if success:
                logger.info("Email configuration test successful", extra={
                    'test_email': test_email
                })
            else:
                logger.warning("Email configuration test failed", extra={
                    'test_email': test_email,
                    'error': message
                })
            return success, message
        except Exception as e:
            error_msg = f"Email test failed: {str(e)}"
            logger.error("Email configuration test exception", extra={
                'test_email': test_email,
                'error': str(e)
            }, exc_info=True)
            return False, error_msg


# Factory function for backward compatibility
def create_email_manager(db_manager: DatabaseManager = None, 
                        ai_manager: AIServiceManager = None) -> EmailManager:
    """Create email manager with dependencies."""
    return EmailManager(db_manager, ai_manager)


# Global email manager instance (optional, for singleton pattern)
_global_email_manager = None


def get_global_email_manager() -> EmailManager:
    """Get or create global email manager instance."""
    global _global_email_manager
    if _global_email_manager is None:
        _global_email_manager = EmailManager()
    return _global_email_manager


def set_global_email_manager(email_manager: EmailManager):
    """Set global email manager instance."""
    global _global_email_manager
    _global_email_manager = email_manager