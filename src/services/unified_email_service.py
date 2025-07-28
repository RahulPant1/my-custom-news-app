"""Unified Email Service - Consolidated and refactored email delivery system."""

import smtplib
import ssl
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Protocol
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.repositories.email_repository import (
    EmailRepository, 
    EmailDelivery, 
    EmailPreferences, 
    FeedbackRecord
)
from src.settings.email_config import EmailServiceConfig
from src.templates.email_templates import render_email_template
from src.oneliner_service import OnelinerGenerationService
from src.utils.common import generate_tracking_url
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AIService(Protocol):
    """Protocol for AI service integration."""
    
    def generate_summary(self, title: str, content: str) -> Dict:
        """Generate AI summary."""
        ...


class UserRepository(Protocol):
    """Protocol for user data access."""
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Get user preferences."""
        ...
    
    def update_user_email(self, user_id: str, email: str) -> bool:
        """Update user email address."""
        ...


class UnifiedEmailService:
    """Unified email service with proper separation of concerns and error handling."""
    
    def __init__(
        self,
        email_repo: EmailRepository,
        user_repo: UserRepository,
        config: EmailServiceConfig,
        ai_service: Optional[AIService] = None
    ):
        self.email_repo = email_repo
        self.user_repo = user_repo
        self.config = config
        self.ai_service = ai_service
        self.oneliner_service = OnelinerGenerationService()
        
        # API call limiting for AI services
        self.max_api_calls = 6
        self.api_call_count = 0
        
        logger.info("Unified email service initialized", extra={
            "max_api_calls": self.max_api_calls,
            "ai_service_available": ai_service is not None
        })
    
    def _reset_api_counter(self):
        """Reset API call counter for new digest generation."""
        self.api_call_count = 0
        logger.debug("API call counter reset")
    
    def _make_ai_call(self, title: str, content: str, fallback: str = None) -> Optional[str]:
        """Make an AI call with rate limiting and proper error handling."""
        if self.api_call_count >= self.max_api_calls:
            logger.warning("API call limit reached", extra={
                "limit": self.max_api_calls,
                "attempted_title": title
            })
            return fallback
        
        if not self.ai_service:
            logger.debug("No AI service available, using fallback")
            return fallback
            
        try:
            self.api_call_count += 1
            logger.info("Making AI call", extra={
                "call_number": self.api_call_count,
                "max_calls": self.max_api_calls,
                "title": title
            })
            
            response = self.ai_service.generate_summary(title, content)
            
            if response.get('success') and response.get('content'):
                result = response['content'].strip().strip('"').strip("'")
                logger.debug("AI call successful", extra={"response_length": len(result)})
                return result
            else:
                error_msg = response.get('error', 'Unknown error')
                logger.warning("AI call failed", extra={"error": error_msg})
                return fallback
                
        except Exception as e:
            logger.error("AI call exception", extra={
                "error": str(e),
                "title": title
            }, exc_info=True)
            return fallback
    
    def send_digest_email(self, user_id: str, digest_data: Dict) -> Tuple[bool, str]:
        """Send digest email to user with comprehensive error handling."""
        try:
            logger.info("Starting digest email delivery", extra={
                "user_id": user_id,
                "category_count": len(digest_data.get('categories', {}))
            })
            
            # Reset API call counter for this email delivery
            self._reset_api_counter()
            
            # Validate user and email
            user_prefs = self.user_repo.get_user_preferences(user_id)
            if not user_prefs:
                error_msg = f"User {user_id} not found"
                logger.error("User not found", extra={"user_id": user_id})
                return False, error_msg
            
            user_email = user_prefs.get('email')
            if not user_email:
                error_msg = f"No email address for user {user_id}"
                logger.error("User email missing", extra={"user_id": user_id})
                return False, error_msg
            
            # Check if email delivery is enabled
            email_prefs = self.email_repo.get_email_preferences(user_id)
            if email_prefs and not email_prefs.email_enabled:
                error_msg = f"Email delivery disabled for user {user_id}"
                logger.info("Email delivery disabled", extra={"user_id": user_id})
                return False, error_msg
            
            # Record delivery attempt first to get delivery_id
            delivery = EmailDelivery(
                id=None,
                user_id=user_id,
                email_address=user_email,
                subject_line="",  # Will be updated after generation
                digest_content=digest_data,
                email_html="",  # Will be updated after generation
                delivery_status='pending',
                delivery_method='smtp'
            )
            
            delivery_id = self.email_repo.record_email_delivery(delivery)
            if not delivery_id:
                error_msg = "Failed to record delivery attempt"
                logger.error("Delivery recording failed", extra={"user_id": user_id})
                return False, error_msg
            
            logger.debug("Delivery recorded", extra={
                "delivery_id": delivery_id,
                "user_id": user_id
            })
            
            # Generate email content with delivery_id for tracking links
            subject = self._generate_subject_line(user_id, digest_data)
            html_content = self._generate_email_html(user_id, digest_data, user_prefs, email_prefs, delivery_id)
            
            # Update delivery record with generated content
            self.email_repo.update_delivery_content(delivery_id, subject, html_content)
            
            # Send email
            success, message = self._send_smtp_email(user_email, subject, html_content)
            
            # Update delivery status
            status = 'sent' if success else 'failed'
            self.email_repo.update_delivery_status(
                delivery_id, status,
                datetime.utcnow().isoformat() if success else None,
                None, None if success else message
            )
            
            if success:
                logger.info("Email delivered successfully", extra={
                    "user_id": user_id,
                    "user_email": user_email,
                    "delivery_id": delivery_id
                })
                return True, f"Email sent to {user_email}"
            else:
                logger.error("Email delivery failed", extra={
                    "user_id": user_id,
                    "user_email": user_email,
                    "delivery_id": delivery_id,
                    "error": message
                })
                return False, message
                
        except Exception as e:
            error_msg = f"Email delivery failed: {str(e)}"
            logger.error("Email delivery exception", extra={
                "user_id": user_id,
                "error": str(e)
            }, exc_info=True)
            return False, error_msg
    
    def _generate_subject_line(self, user_id: str, digest_data: Dict) -> str:
        """Generate personalized subject line with AI assistance."""
        try:
            # Build AI context for subject generation
            categories = list(digest_data.get('categories', {}).keys())
            article_count = sum(len(articles) for articles in digest_data.get('categories', {}).values())
            
            context = f"""Generate a personalized email subject line for a news digest with:
- {article_count} articles
- Categories: {', '.join(categories)}

Make it engaging, specific, and under 60 characters."""
            
            # Use rate-limited AI call with fallback
            fallback_subject = self._generate_engaging_subject(categories)
            
            subject = self._make_ai_call("Subject Generation", context, fallback_subject)
            if subject and len(subject) <= self.config.max_subject_length:
                logger.debug("AI-generated subject line", extra={
                    "user_id": user_id,
                    "subject_length": len(subject)
                })
                return subject
            
        except Exception as e:
            logger.warning("Failed to generate AI subject line", extra={
                "user_id": user_id,
                "error": str(e)
            })
        
        # Fallback to template-based subject
        categories = list(digest_data.get('categories', {}).keys())
        fallback = self._generate_engaging_subject(categories)
        logger.debug("Using fallback subject line", extra={"user_id": user_id})
        return fallback
    
    def _generate_engaging_subject(self, categories: List[str]) -> str:
        """Generate engaging email subject lines using templates."""
        import random
        from datetime import datetime
        
        # Get current date info
        now = datetime.now()
        day_name = now.strftime('%A')
        date_str = now.strftime('%b %d')
        
        # Subject line templates by category
        if len(categories) == 1:
            category = categories[0]
            category_subjects = {
                'Technology & Gadgets': [
                    f"🚀 Tech Breakthroughs This {day_name}",
                    f"💻 Latest Tech Innovations - {date_str}",
                    f"⚡ Tech News That Matters - {day_name}",
                    f"🔥 Hot Tech Updates for {date_str}"
                ],
                'Science & Discovery': [
                    f"🔬 Amazing Science Discoveries - {day_name}",
                    f"🌟 Scientific Breakthroughs This Week",
                    f"🧪 Science News That Will Amaze You",
                    f"🌌 Discover the Universe - {date_str}"
                ],
                'Health & Wellness': [
                    f"💪 Your Health Update - {day_name}",
                    f"🏥 Wellness News for {date_str}",
                    f"❤️ Health Insights This {day_name}",
                    f"🌿 Healthy Living Updates"
                ],
                'Business & Finance': [
                    f"💼 Market Moves & Money Matters",
                    f"📈 Business News That Counts - {date_str}",
                    f"💰 Financial Updates This {day_name}",
                    f"🏢 Business Insights for {date_str}"
                ],
                'Global Affairs': [
                    f"🌍 World News Roundup - {day_name}",
                    f"🌐 Global Headlines for {date_str}",
                    f"📰 What's Happening Worldwide",
                    f"🗺️ International News Digest"
                ],
                'Environment & Climate': [
                    f"🌱 Planet Updates - {day_name}",
                    f"🌍 Climate & Environment News",
                    f"♻️ Green News for {date_str}",
                    f"🌿 Sustainability Updates This {day_name}"
                ],
                'Good Vibes (Positive News)': [
                    f"😊 Good News to Brighten Your {day_name}",
                    f"🌈 Positive Vibes for {date_str}",
                    f"✨ Uplifting Stories This {day_name}",
                    f"🎉 Feel-Good News Digest"
                ]
            }
            
            # Return random subject for the category
            subjects = category_subjects.get(category, [f"📰 {category} News - {date_str}"])
            return random.choice(subjects)
        
        else:
            # Multi-category subject lines
            multi_subjects = [
                f"📰 Your Personalized News Briefing - {day_name}",
                f"🌟 Today's Top Stories Just for You",
                f"📱 Your Daily News Roundup - {date_str}",
                f"🔥 Hot Topics & Headlines This {day_name}",
                f"📰 News Digest: {len(categories)} Topics - {date_str}",
                f"⚡ Breaking Down Today's Big Stories",
                f"🎯 Curated News for {day_name}",
                f"📊 Your News Mix - {date_str}",
                f"🌍 World + Local Updates This {day_name}",
                f"📈 News That Matters to You"
            ]
            return random.choice(multi_subjects)
    
    def _generate_email_html(self, user_id: str, digest_data: Dict, 
                           user_prefs: Dict, email_prefs: Optional[EmailPreferences], 
                           delivery_id: int = None) -> str:
        """Generate HTML email content using unified template system."""
        # Extract highlights using the one-liner service
        highlights = self._extract_highlights(digest_data, user_prefs)
        
        # Prepare template data
        template_data = {
            'user_id': user_id,
            'categories': digest_data.get('categories', {}),
            'user_prefs': user_prefs,
            'email_prefs': {
                'include_feedback_links': email_prefs.include_feedback_links if email_prefs else True,
                'include_social_sharing': email_prefs.include_social_sharing if email_prefs else True
            } if email_prefs else {'include_feedback_links': True, 'include_social_sharing': True},
            'highlights': highlights,
            'base_url': self.config.base_url,
            'unsubscribe_url': f"{self.config.base_url}/unsubscribe?user_id={user_id}",
            'delivery_id': delivery_id
        }
        
        # Use random template selection for variety
        return render_email_template('random', template_data)
    
    def _extract_highlights(self, digest_data: Dict, user_prefs: Dict = None) -> Dict:
        """Extract highlights using the one-liner service."""
        highlights = {
            'top_stat': None,
            'top_quote': None,
            'one_liner': None,
            'trending_topic': None
        }
        
        try:
            # Get user's preferred categories for targeted one-liners
            user_categories = None
            if user_prefs:
                selected_cats = user_prefs.get('selected_categories', [])
                if isinstance(selected_cats, str):
                    try:
                        import json
                        user_categories = json.loads(selected_cats)
                    except:
                        user_categories = [selected_cats]
                elif isinstance(selected_cats, list):
                    user_categories = selected_cats
            
            # Get random one-liner from the database
            one_liner = self.oneliner_service.get_random_highlight(user_categories)
            if one_liner:
                highlights['one_liner'] = one_liner
            
            # Extract trending topic from digest data
            categories = list(digest_data.get('categories', {}).keys())
            if categories:
                highlights['trending_topic'] = categories[0]
                
            logger.debug("Highlights extracted", extra={
                "has_one_liner": bool(highlights['one_liner']),
                "trending_topic": highlights['trending_topic']
            })
                
        except Exception as e:
            logger.warning("Failed to extract highlights", extra={"error": str(e)})
            # Fallback one-liner
            highlights['one_liner'] = "Stay informed with today's most important developments."
        
        return highlights
    
    def _send_smtp_email(self, to_email: str, subject: str, html_content: str) -> Tuple[bool, str]:
        """Send email via SMTP with comprehensive error handling."""
        try:
            # Validate content length
            if len(html_content) > self.config.max_content_length:
                error_msg = f"Email content too large: {len(html_content)} bytes"
                logger.error("Content size limit exceeded", extra={
                    "content_size": len(html_content),
                    "max_size": self.config.max_content_length
                })
                return False, error_msg
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject[:self.config.max_subject_length]
            msg['From'] = f"{self.config.smtp.from_name} <{self.config.smtp.from_email}>"
            msg['To'] = to_email
            
            # Add HTML part
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            logger.debug("SMTP message prepared", extra={
                "to_email": to_email,
                "subject_length": len(subject),
                "content_length": len(html_content)
            })
            
            # Send email
            if self.config.smtp.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.config.smtp.server, self.config.smtp.port) as server:
                    server.starttls(context=context)
                    server.login(self.config.smtp.username, self.config.smtp.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.config.smtp.server, self.config.smtp.port) as server:
                    server.login(self.config.smtp.username, self.config.smtp.password)
                    server.send_message(msg)
            
            logger.info("SMTP email sent successfully", extra={"to_email": to_email})
            return True, "Email sent successfully"
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP Authentication failed: {e}"
            logger.error("SMTP authentication error", extra={"error": str(e)})
            return False, error_msg
        except smtplib.SMTPRecipientsRefused as e:
            error_msg = f"Recipient refused: {e}"
            logger.error("SMTP recipient refused", extra={"error": str(e)})
            return False, error_msg
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {e}"
            logger.error("SMTP error", extra={"error": str(e)})
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error("Unexpected SMTP error", extra={"error": str(e)}, exc_info=True)
            return False, error_msg
    
    # User preference management methods
    def get_user_email_preferences(self, user_id: str) -> Optional[EmailPreferences]:
        """Get email preferences for a user."""
        return self.email_repo.get_email_preferences(user_id)
    
    def update_email_preferences(self, user_id: str, preferences_dict: Dict) -> bool:
        """Update email preferences for a user."""
        current_prefs = self.email_repo.get_email_preferences(user_id)
        
        if current_prefs:
            # Update existing preferences
            updated_prefs = EmailPreferences(
                user_id=user_id,
                email_enabled=preferences_dict.get('email_enabled', current_prefs.email_enabled),
                delivery_frequency=preferences_dict.get('delivery_frequency', current_prefs.delivery_frequency),
                delivery_time=preferences_dict.get('delivery_time', current_prefs.delivery_time),
                delivery_timezone=preferences_dict.get('delivery_timezone', current_prefs.delivery_timezone),
                email_format=preferences_dict.get('email_format', current_prefs.email_format),
                include_feedback_links=preferences_dict.get('include_feedback_links', current_prefs.include_feedback_links),
                include_social_sharing=preferences_dict.get('include_social_sharing', current_prefs.include_social_sharing),
                personalized_subject=preferences_dict.get('personalized_subject', current_prefs.personalized_subject)
            )
        else:
            # Create new preferences with defaults
            updated_prefs = EmailPreferences(
                user_id=user_id,
                email_enabled=preferences_dict.get('email_enabled', True),
                delivery_frequency=preferences_dict.get('delivery_frequency', 'daily'),
                delivery_time=preferences_dict.get('delivery_time', '08:00'),
                delivery_timezone=preferences_dict.get('delivery_timezone', 'UTC'),
                email_format=preferences_dict.get('email_format', 'html'),
                include_feedback_links=preferences_dict.get('include_feedback_links', True),
                include_social_sharing=preferences_dict.get('include_social_sharing', True),
                personalized_subject=preferences_dict.get('personalized_subject', True)
            )
        
        success = self.email_repo.save_email_preferences(updated_prefs)
        if success:
            logger.info("Email preferences updated", extra={
                "user_id": user_id,
                "preferences": preferences_dict
            })
        else:
            logger.error("Failed to update email preferences", extra={"user_id": user_id})
        
        return success
    
    # Feedback and engagement methods
    def record_user_feedback(self, user_id: str, article_id: int, feedback_type: str,
                           email_delivery_id: int = None, share_platform: str = None) -> bool:
        """Record user feedback and update engagement metrics."""
        feedback = FeedbackRecord(
            id=None,
            user_id=user_id,
            article_id=article_id,
            email_delivery_id=email_delivery_id,
            feedback_type=feedback_type,
            feedback_source='email',
            share_platform=share_platform
        )
        
        # Record feedback
        success = self.email_repo.record_feedback(feedback)
        
        if success:
            # Update engagement metrics
            self.email_repo.update_engagement_metrics(user_id, feedback_type, share_platform)
            logger.info("User feedback recorded", extra={
                "user_id": user_id,
                "article_id": article_id,
                "feedback_type": feedback_type,
                "share_platform": share_platform
            })
        else:
            logger.error("Failed to record user feedback", extra={
                "user_id": user_id,
                "article_id": article_id,
                "feedback_type": feedback_type
            })
        
        return success
    
    def get_user_engagement_summary(self, user_id: str, days: int = 30) -> Dict:
        """Get engagement summary for a user."""
        return self.email_repo.get_user_engagement_summary(user_id, days)
    
    def get_delivery_history(self, user_id: str, limit: int = 10) -> List[EmailDelivery]:
        """Get recent email delivery history for a user."""
        return self.email_repo.get_delivery_history(user_id, limit)


class UnifiedEmailServiceFactory:
    """Factory for creating unified email service instances with proper dependency injection."""
    
    @staticmethod
    def create_email_service(
        db_path: str,
        user_repo: UserRepository,
        config: EmailServiceConfig,
        ai_service: Optional[AIService] = None
    ) -> UnifiedEmailService:
        """Create unified email service with dependencies."""
        email_repo = EmailRepository(db_path)
        
        return UnifiedEmailService(
            email_repo=email_repo,
            user_repo=user_repo,
            config=config,
            ai_service=ai_service
        )