"""Refactored email delivery system with proper architecture and dependency injection."""

import logging
from typing import Dict, Tuple, Optional, List
from datetime import datetime

from src.settings.email_config import get_email_config, validate_email_setup
from src.services.email_service import EmailServiceFactory, AIService, UserRepository
from src.database import DatabaseManager
from src.enhanced_ai_processor import EnhancedAIProcessor

logger = logging.getLogger(__name__)


class DatabaseUserRepository:
    """Adapter to make DatabaseManager compatible with UserRepository protocol."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Get user preferences."""
        return self.db_manager.get_user_preferences(user_id)
    
    def update_user_email(self, user_id: str, email: str) -> bool:
        """Update user email address."""
        return self.db_manager.update_user_email(user_id, email)


class AIServiceAdapter:
    """Adapter to make EnhancedAIProcessor compatible with AIService protocol."""
    
    def __init__(self, ai_processor: EnhancedAIProcessor):
        self.ai_processor = ai_processor
    
    def generate_summary(self, title: str, content: str) -> Dict:
        """Generate AI summary."""
        try:
            # Use the enhanced AI processor's method
            summary = self.ai_processor.generate_summary_enhanced(title, content)
            return {
                'success': bool(summary and summary.strip()),
                'content': summary,
                'provider': 'llm_router',
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'content': None,
                'provider': None,
                'error': str(e)
            }


class RefactoredEmailDeliveryManager:
    """Modern email delivery manager with proper architecture."""
    
    def __init__(self, db_manager: DatabaseManager = None, ai_processor: EnhancedAIProcessor = None):
        self.db_manager = db_manager or DatabaseManager()
        self.ai_processor = ai_processor
        
        # Validate email configuration
        config_status = validate_email_setup()
        if not config_status['valid']:
            logger.warning(f"Email configuration issues: {config_status['errors']}")
            self.config = None
            self.email_service = None
        else:
            try:
                self.config = get_email_config()
                
                # Create adapters
                user_repo = DatabaseUserRepository(self.db_manager)
                ai_service = AIServiceAdapter(self.ai_processor) if self.ai_processor else None
                
                # Create email service with dependency injection
                self.email_service = EmailServiceFactory.create_email_service(
                    db_path=self.db_manager.db_path,
                    user_repo=user_repo,
                    config=self.config,
                    ai_service=ai_service
                )
                
                logger.info("Email delivery system initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize email service: {e}")
                self.config = None
                self.email_service = None
    
    def is_configured(self) -> bool:
        """Check if email system is properly configured."""
        return self.email_service is not None
    
    def deliver_digest_email(self, user_id: str, digest_data: Dict) -> Tuple[bool, str]:
        """Deliver digest email using refactored service architecture."""
        if not self.is_configured():
            return False, "Email system not configured. Check SMTP settings in .env file"
        
        try:
            return self.email_service.send_digest_email(user_id, digest_data)
        except Exception as e:
            error_msg = f"Email delivery failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_email_preferences(self, user_id: str) -> Optional[Dict]:
        """Get email preferences for a user."""
        if not self.is_configured():
            return None
        
        prefs = self.email_service.get_user_email_preferences(user_id)
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
    
    def update_email_preferences(self, user_id: str, preferences: Dict) -> bool:
        """Update email preferences for a user."""
        if not self.is_configured():
            return False
        
        return self.email_service.update_email_preferences(user_id, preferences)
    
    def record_feedback(self, user_id: str, article_id: int, feedback_type: str,
                       email_delivery_id: int = None, share_platform: str = None) -> bool:
        """Record user feedback."""
        if not self.is_configured():
            return False
        
        return self.email_service.record_user_feedback(
            user_id, article_id, feedback_type, email_delivery_id, share_platform
        )
    
    def get_engagement_summary(self, user_id: str, days: int = 30) -> Dict:
        """Get user engagement summary."""
        if not self.is_configured():
            return {}
        
        return self.email_service.get_user_engagement_summary(user_id, days)
    
    def get_delivery_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get delivery history for a user."""
        if not self.is_configured():
            return []
        
        deliveries = self.email_service.get_delivery_history(user_id, limit)
        
        # Convert to dict format for compatibility
        return [{
            'id': delivery.id,
            'email_address': delivery.email_address,
            'subject_line': delivery.subject_line,
            'delivery_status': delivery.delivery_status,
            'sent_at': delivery.sent_at,
            'error_message': delivery.error_message,
            'created_at': delivery.created_at
        } for delivery in deliveries]
    
    def get_configuration_status(self) -> Dict:
        """Get detailed configuration status."""
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
    
    def generate_html_email(self, user_id: str, digest_data: Dict) -> str:
        """Generate HTML email content for preview."""
        try:
            # Import the email template manager
            from .templates.email_templates import EmailTemplateManager
            
            # Create template manager
            template_manager = EmailTemplateManager()
            
            # Get user preferences for template data
            user_prefs = self.db_manager.get_user_preferences(user_id)
            if not user_prefs:
                raise ValueError(f"User {user_id} not found")
            
            # Create complete template data with all required fields
            template_data = {
                'user_id': user_id,
                'categories': digest_data.get('categories', {}),
                'generated_at': digest_data.get('generated_at', datetime.now().isoformat()),
                'base_url': 'http://localhost:5000',
                # Required template fields that were missing:
                'user_prefs': {
                    'user_id': user_id,
                    'email': user_prefs.get('email', ''),
                    'selected_categories': user_prefs.get('selected_categories', []),
                    'digest_frequency': user_prefs.get('digest_frequency', 'daily'),
                    'articles_per_digest': user_prefs.get('articles_per_digest', 10)
                },
                'email_prefs': {
                    'email_enabled': True,
                    'delivery_frequency': user_prefs.get('digest_frequency', 'daily'),
                    'delivery_time': '08:00',
                    'delivery_timezone': 'UTC',
                    'email_format': 'html',
                    'include_feedback_links': True,
                    'include_social_sharing': True,
                    'personalized_subject': True
                },
                'highlights': {
                    'trending_count': sum(1 for articles in digest_data.get('categories', {}).values() 
                                        for article in articles if article.get('trending_flag')),
                    'total_articles': sum(len(articles) for articles in digest_data.get('categories', {}).values()),
                    'categories_count': len(digest_data.get('categories', {})),
                    'has_images': any(article.get('image_url', '').startswith(('http://', 'https://'))
                                    for articles in digest_data.get('categories', {}).values() 
                                    for article in articles)
                },
                'unsubscribe_url': f"http://localhost:5000/unsubscribe/{user_id}",
                'delivery_id': f"preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            }
            
            # Use mobile_card template for preview (best looking)
            html_content = template_manager.render_template('mobile_card', template_data)
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error generating HTML email preview: {e}")
            # Return a simple fallback HTML with better error details
            categories = digest_data.get('categories', {})
            article_count = sum(len(articles) for articles in categories.values())
            
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>News Digest Preview - Error</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
                    .error {{ color: #d32f2f; background: #ffebee; padding: 15px; border-radius: 4px; margin: 20px 0; }}
                    .stats {{ background: #e3f2fd; padding: 15px; border-radius: 4px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>📰 News Digest Preview</h1>
                    <div class="stats">
                        <p><strong>User:</strong> {user_id}</p>
                        <p><strong>Articles:</strong> {article_count} articles across {len(categories)} categories</p>
                        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                    <div class="error">
                        <h3>Template Error</h3>
                        <p><strong>Error:</strong> {str(e)}</p>
                        <p>The email template could not be rendered, but this preview shows your digest data is available.</p>
                    </div>
                    <div class="stats">
                        <h3>Available Categories:</h3>
                        <ul>
                        {''.join(f'<li><strong>{category}:</strong> {len(articles)} articles</li>' 
                                for category, articles in categories.items())}
                        </ul>
                    </div>
                </div>
            </body>
            </html>
            """


# Backward compatibility function
def create_email_delivery_manager(db_manager: DatabaseManager = None, 
                                ai_processor: EnhancedAIProcessor = None) -> RefactoredEmailDeliveryManager:
    """Create email delivery manager with enhanced AI processor."""
    return RefactoredEmailDeliveryManager(db_manager, ai_processor)