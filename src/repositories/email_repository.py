"""Email-specific database operations with proper separation of concerns."""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmailDelivery:
    """Email delivery record."""
    id: Optional[int]
    user_id: str
    email_address: str
    subject_line: str
    digest_content: Dict
    email_html: str
    delivery_status: str
    delivery_method: str
    sent_at: Optional[str] = None
    delivery_id: Optional[str] = None
    error_message: Optional[str] = None
    open_count: int = 0
    click_count: int = 0
    created_at: Optional[str] = None


@dataclass
class EmailPreferences:
    """User email preferences."""
    user_id: str
    email_enabled: bool = True
    delivery_frequency: str = 'daily'
    delivery_time: str = '08:00'
    delivery_timezone: str = 'UTC'
    email_format: str = 'html'
    include_feedback_links: bool = True
    include_social_sharing: bool = True
    personalized_subject: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class FeedbackRecord:
    """User feedback record."""
    id: Optional[int]
    user_id: str
    article_id: int
    email_delivery_id: Optional[int]
    feedback_type: str
    feedback_source: str = 'email'
    share_platform: Optional[str] = None
    created_at: Optional[str] = None


class EmailRepository:
    """Repository for email-related database operations."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def record_email_delivery(self, delivery: EmailDelivery) -> Optional[int]:
        """Record an email delivery attempt."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO email_deliveries 
                    (user_id, email_address, subject_line, digest_content, email_html, 
                     delivery_method, delivery_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    delivery.user_id, 
                    delivery.email_address, 
                    delivery.subject_line,
                    json.dumps(delivery.digest_content), 
                    delivery.email_html,
                    delivery.delivery_method,
                    delivery.delivery_status or 'pending'
                ))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error recording email delivery: {e}")
            return None
    
    def update_delivery_status(self, delivery_id: int, status: str, 
                             sent_at: str = None, external_id: str = None, 
                             error_message: str = None) -> bool:
        """Update email delivery status."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE email_deliveries 
                    SET delivery_status = ?, sent_at = ?, delivery_id = ?, error_message = ?
                    WHERE id = ?
                ''', (
                    status, 
                    sent_at or datetime.utcnow().isoformat(),
                    external_id, 
                    error_message, 
                    delivery_id
                ))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating delivery status: {e}")
            return False
    
    def update_delivery_content(self, delivery_id: int, subject_line: str, email_html: str) -> bool:
        """Update email delivery content after generation."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE email_deliveries 
                    SET subject_line = ?, email_html = ?
                    WHERE id = ?
                ''', (subject_line, email_html, delivery_id))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating delivery content: {e}")
            return False
    
    def get_email_preferences(self, user_id: str) -> Optional[EmailPreferences]:
        """Get email preferences for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM email_preferences WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                
                if row:
                    return EmailPreferences(
                        user_id=row[0],
                        email_enabled=bool(row[1]),
                        delivery_frequency=row[2],
                        delivery_time=row[3],
                        delivery_timezone=row[4],
                        email_format=row[5],
                        include_feedback_links=bool(row[6]),
                        include_social_sharing=bool(row[7]),
                        personalized_subject=bool(row[8]),
                        created_at=row[9],
                        updated_at=row[10]
                    )
                return None
        except Exception as e:
            logger.error(f"Error getting email preferences: {e}")
            return None
    
    def save_email_preferences(self, preferences: EmailPreferences) -> bool:
        """Save email preferences for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO email_preferences 
                    (user_id, email_enabled, delivery_frequency, delivery_time, delivery_timezone,
                     email_format, include_feedback_links, include_social_sharing, personalized_subject,
                     updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    preferences.user_id,
                    preferences.email_enabled,
                    preferences.delivery_frequency,
                    preferences.delivery_time,
                    preferences.delivery_timezone,
                    preferences.email_format,
                    preferences.include_feedback_links,
                    preferences.include_social_sharing,
                    preferences.personalized_subject
                ))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error saving email preferences: {e}")
            return False
    
    def record_feedback(self, feedback: FeedbackRecord) -> bool:
        """Record user feedback on an article."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO feedback_history 
                    (user_id, article_id, email_delivery_id, feedback_type, 
                     feedback_source, share_platform)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    feedback.user_id,
                    feedback.article_id,
                    feedback.email_delivery_id,
                    feedback.feedback_type,
                    feedback.feedback_source,
                    feedback.share_platform
                ))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error recording feedback: {e}")
            return False
    
    def get_user_engagement_summary(self, user_id: str, days: int = 30) -> Dict:
        """Get engagement summary for a user over the last N days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        SUM(emails_sent) as total_emails,
                        SUM(emails_opened) as total_opens,
                        SUM(total_clicks) as total_clicks,
                        SUM(articles_liked) as total_likes,
                        SUM(articles_disliked) as total_dislikes,
                        SUM(shares_total) as total_shares,
                        AVG(total_clicks * 1.0 / NULLIF(emails_sent, 0)) as avg_click_rate
                    FROM engagement_metrics 
                    WHERE user_id = ? AND metric_date >= date('now', '-{} days')
                '''.format(days), (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'total_emails': row[0] or 0,
                        'total_opens': row[1] or 0,
                        'total_clicks': row[2] or 0,
                        'total_likes': row[3] or 0,
                        'total_dislikes': row[4] or 0,
                        'total_shares': row[5] or 0,
                        'avg_click_rate': round(row[6] or 0, 3)
                    }
                return {}
        except Exception as e:
            logger.error(f"Error getting engagement summary: {e}")
            return {}
    
    def get_delivery_history(self, user_id: str, limit: int = 10) -> List[EmailDelivery]:
        """Get recent email delivery history for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, user_id, email_address, subject_line, digest_content, email_html,
                           delivery_status, delivery_method, sent_at, delivery_id, error_message,
                           open_count, click_count, created_at
                    FROM email_deliveries 
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (user_id, limit))
                
                deliveries = []
                for row in cursor.fetchall():
                    try:
                        digest_content = json.loads(row[4]) if row[4] else {}
                    except:
                        digest_content = {}
                    
                    deliveries.append(EmailDelivery(
                        id=row[0],
                        user_id=row[1],
                        email_address=row[2],
                        subject_line=row[3],
                        digest_content=digest_content,
                        email_html=row[5],
                        delivery_status=row[6],
                        delivery_method=row[7],
                        sent_at=row[8],
                        delivery_id=row[9],
                        error_message=row[10],
                        open_count=row[11],
                        click_count=row[12],
                        created_at=row[13]
                    ))
                
                return deliveries
        except Exception as e:
            logger.error(f"Error getting delivery history: {e}")
            return []
    
    def update_engagement_metrics(self, user_id: str, feedback_type: str, 
                                share_platform: str = None) -> bool:
        """Update daily engagement metrics for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                today = datetime.utcnow().strftime('%Y-%m-%d')
                
                # Insert or get existing metrics for today
                cursor.execute('''
                    INSERT OR IGNORE INTO engagement_metrics (user_id, metric_date)
                    VALUES (?, ?)
                ''', (user_id, today))
                
                # Update specific metrics based on feedback type
                if feedback_type == 'like':
                    cursor.execute('''
                        UPDATE engagement_metrics 
                        SET articles_liked = articles_liked + 1, total_clicks = total_clicks + 1
                        WHERE user_id = ? AND metric_date = ?
                    ''', (user_id, today))
                elif feedback_type == 'dislike':
                    cursor.execute('''
                        UPDATE engagement_metrics 
                        SET articles_disliked = articles_disliked + 1, total_clicks = total_clicks + 1
                        WHERE user_id = ? AND metric_date = ?
                    ''', (user_id, today))
                elif feedback_type == 'share':
                    update_query = '''
                        UPDATE engagement_metrics 
                        SET shares_total = shares_total + 1, total_clicks = total_clicks + 1
                    '''
                    params = [user_id, today]
                    
                    if share_platform == 'twitter':
                        update_query += ', shares_twitter = shares_twitter + 1'
                    elif share_platform == 'linkedin':
                        update_query += ', shares_linkedin = shares_linkedin + 1'
                    elif share_platform == 'whatsapp':
                        update_query += ', shares_whatsapp = shares_whatsapp + 1'
                    
                    update_query += ' WHERE user_id = ? AND metric_date = ?'
                    cursor.execute(update_query, params)
                else:  # more_like_this, click, etc.
                    cursor.execute('''
                        UPDATE engagement_metrics 
                        SET total_clicks = total_clicks + 1
                        WHERE user_id = ? AND metric_date = ?
                    ''', (user_id, today))
                
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error updating engagement metrics: {e}")
            return False