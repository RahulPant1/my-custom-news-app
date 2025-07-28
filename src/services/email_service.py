"""Professional email service with dependency injection and proper error handling."""

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

logger = logging.getLogger(__name__)


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


class EmailDeliveryService:
    """Service for email delivery with proper separation of concerns."""
    
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
        
        # API call limiting
        self.max_api_calls = 6
        self.api_call_count = 0
    
    def _reset_api_counter(self):
        """Reset API call counter for new digest generation."""
        self.api_call_count = 0
    
    def _make_ai_call(self, title: str, content: str, fallback: str = None) -> Optional[str]:
        """Make an AI call with rate limiting. Returns None if limit exceeded."""
        if self.api_call_count >= self.max_api_calls:
            logger.warning(f"API call limit ({self.max_api_calls}) reached. Using fallback.")
            return fallback
        
        if not self.ai_service:
            return fallback
            
        try:
            self.api_call_count += 1
            logger.info(f"Making AI call {self.api_call_count}/{self.max_api_calls}: {title}")
            response = self.ai_service.generate_summary(title, content)
            
            if response.get('success') and response.get('content'):
                return response['content'].strip().strip('"').strip("'")
            else:
                logger.warning(f"AI call failed: {response.get('error', 'Unknown error')}")
                return fallback
        except Exception as e:
            logger.error(f"AI call error: {e}")
            return fallback
    
    def send_digest_email(self, user_id: str, digest_data: Dict) -> Tuple[bool, str]:
        """Send digest email to user with comprehensive error handling."""
        try:
            # Reset API call counter for this email delivery
            self._reset_api_counter()
            
            # Validate user and email
            user_prefs = self.user_repo.get_user_preferences(user_id)
            if not user_prefs:
                return False, f"User {user_id} not found"
            
            user_email = user_prefs.get('email')
            if not user_email:
                return False, f"No email address for user {user_id}"
            
            # Check if email delivery is enabled
            email_prefs = self.email_repo.get_email_preferences(user_id)
            if email_prefs and not email_prefs.email_enabled:
                return False, f"Email delivery disabled for user {user_id}"
            
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
                return False, "Failed to record delivery attempt"
            
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
                logger.info(f"Email delivered successfully to {user_email}")
                return True, f"Email sent to {user_email}"
            else:
                logger.error(f"Email delivery failed to {user_email}: {message}")
                return False, message
                
        except Exception as e:
            error_msg = f"Email delivery failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _generate_subject_line(self, user_id: str, digest_data: Dict) -> str:
        """Generate personalized subject line."""
        try:
            # Build AI context for subject generation
            categories = list(digest_data.get('categories', {}).keys())
            article_count = sum(len(articles) for articles in digest_data.get('categories', {}).values())
            
            context = f"""Generate a personalized email subject line for a news digest with:
- {article_count} articles
- Categories: {', '.join(categories)}

Make it engaging, specific, and under 60 characters."""
            
            # Use rate-limited AI call with fallback
            categories = list(digest_data.get('categories', {}).keys())
            fallback_subject = self._generate_engaging_subject(categories)
            
            subject = self._make_ai_call("Subject Generation", context, fallback_subject)
            if subject and len(subject) <= self.config.max_subject_length:
                return subject
            
        except Exception as e:
            logger.warning(f"Failed to generate AI subject line: {e}")
        
        # Fallback to template-based subject
        categories = list(digest_data.get('categories', {}).keys())
        return self._generate_engaging_subject(categories)
    
    def _generate_engaging_subject(self, categories: List[str]) -> str:
        """Generate engaging email subject lines."""
        import random
        from datetime import datetime
        
        # Get current date info
        now = datetime.now()
        day_name = now.strftime('%A')
        date_str = now.strftime('%b %d')
        
        # Engaging subject line templates
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
                ],
                'Pop Culture & Lifestyle': [
                    f"🎭 Culture & Lifestyle Update",
                    f"🌟 Pop Culture Buzz for {date_str}",
                    f"📺 Entertainment News This {day_name}",
                    f"🎨 Lifestyle & Culture Digest"
                ],
                'For Young Minds (Youth-Focused)': [
                    f"🎓 News for Young Minds - {day_name}",
                    f"🧠 Youth-Focused Updates",
                    f"📚 Learning & Growth News",
                    f"🌟 Inspiring News for Youth"
                ],
                'DIY, Skills & How-To': [
                    f"🔧 DIY & Skills Update",
                    f"🛠️ Learn Something New This {day_name}",
                    f"📖 How-To & Skills News",
                    f"💡 Creative Ideas for {date_str}"
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
        """Generate HTML email content using template system."""
        # Extract highlights using the new one-liner service
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
            'delivery_id': delivery_id  # Add delivery_id for tracking
        }
        
        return render_email_template('random', template_data)
    
    def _extract_highlights(self, digest_data: Dict, user_prefs: Dict = None) -> Dict:
        """Extract highlights using the new one-liner service."""
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
                
        except Exception as e:
            logger.warning(f"Failed to extract highlights: {e}")
            # Fallback one-liner
            highlights['one_liner'] = "Stay informed with today's most important developments."
        
        return highlights
    
    def _send_smtp_email(self, to_email: str, subject: str, html_content: str) -> Tuple[bool, str]:
        """Send email via SMTP with proper error handling."""
        try:
            # Validate content length
            if len(html_content) > self.config.max_content_length:
                return False, "Email content too large"
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject[:self.config.max_subject_length]
            msg['From'] = f"{self.config.smtp.from_name} <{self.config.smtp.from_email}>"
            msg['To'] = to_email
            
            # Add HTML part
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
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
            
            return True, "Email sent successfully"
            
        except smtplib.SMTPAuthenticationError as e:
            return False, f"SMTP Authentication failed: {e}"
        except smtplib.SMTPRecipientsRefused as e:
            return False, f"Recipient refused: {e}"
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"
    
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
            # Create new preferences
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
        
        return self.email_repo.save_email_preferences(updated_prefs)
    
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
        
        return success
    
    def get_user_engagement_summary(self, user_id: str, days: int = 30) -> Dict:
        """Get engagement summary for a user."""
        return self.email_repo.get_user_engagement_summary(user_id, days)
    
    def get_delivery_history(self, user_id: str, limit: int = 10) -> List[EmailDelivery]:
        """Get recent email delivery history for a user."""
        return self.email_repo.get_delivery_history(user_id, limit)


class EmailServiceFactory:
    """Factory for creating email service instances with proper dependency injection."""
    
    @staticmethod
    def create_email_service(
        db_path: str,
        user_repo: UserRepository,
        config: EmailServiceConfig,
        ai_service: Optional[AIService] = None
    ) -> EmailDeliveryService:
        """Create email service with dependencies."""
        email_repo = EmailRepository(db_path)
        
        return EmailDeliveryService(
            email_repo=email_repo,
            user_repo=user_repo,
            config=config,
            ai_service=ai_service
        )