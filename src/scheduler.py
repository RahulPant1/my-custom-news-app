"""Email digest scheduler for automated delivery."""

import os
import sys
import time
import logging
import schedule
from datetime import datetime, timedelta
from typing import Dict, List
import json

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.database import DatabaseManager
from src.email_delivery_refactored import RefactoredEmailDeliveryManager
from src.enhanced_ai_processor import EnhancedAIProcessor
from src.oneliner_service import OnelinerGenerationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DigestScheduler:
    """Automated email digest scheduler."""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.ai_processor = EnhancedAIProcessor()
        self.email_manager = RefactoredEmailDeliveryManager(
            db_manager=self.db_manager,
            ai_processor=self.ai_processor
        )
        self.oneliner_service = OnelinerGenerationService()
        self.running = False
        
    def get_users_by_frequency(self, frequency: str) -> List[Dict]:
        """Get users with specific digest frequency."""
        try:
            import sqlite3
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, email, selected_categories, digest_frequency, articles_per_digest
                    FROM user_preferences 
                    WHERE digest_frequency = ? AND email IS NOT NULL AND email != ''
                ''', (frequency,))
                
                users = []
                for row in cursor.fetchall():
                    users.append({
                        'user_id': row[0],
                        'email': row[1],
                        'categories': json.loads(row[2]) if row[2] else [],
                        'frequency': row[3],
                        'articles_per_digest': row[4] or 10
                    })
                return users
        except Exception as e:
            logger.error(f"Error getting users by frequency {frequency}: {e}")
            return []
    
    def send_scheduled_digest(self, user_id: str) -> bool:
        """Send digest to a specific user."""
        try:
            logger.info(f"📧 Sending scheduled digest to user: {user_id}")
            
            # Get user preferences
            user_prefs = self.db_manager.get_user_preferences(user_id)
            if not user_prefs:
                logger.error(f"User {user_id} not found")
                return False
            
            if not user_prefs.get('email'):
                logger.error(f"No email address for user {user_id}")
                return False
            
            # Generate digest data
            from src.user_interface import DigestGenerator
            digest_gen = DigestGenerator(self.db_manager)
            articles = digest_gen.get_personalized_articles(user_id)
            
            if not articles:
                logger.warning(f"No articles found for user {user_id}")
                return False
            
            # Group articles by category for email (ensuring no duplicates)
            by_category = {}
            processed_articles = set()  # Track by article ID to prevent duplicates
            user_categories = user_prefs.get('selected_categories', [])
            
            for article in articles:
                article_id = article.get('id')
                if article_id in processed_articles:
                    continue
                    
                categories = article.get('ai_categories', [])
                if isinstance(categories, str):
                    import json
                    try:
                        categories = json.loads(categories)
                    except:
                        categories = []
                
                # Find the best matching category for this article
                best_category = None
                for user_cat in user_categories:
                    if user_cat in categories:
                        best_category = user_cat
                        break
                
                # If no preferred category match, use first available category
                if not best_category and categories:
                    for cat in categories:
                        if cat in user_categories:
                            best_category = cat
                            break
                
                # Add article to the best category only
                if best_category:
                    if best_category not in by_category:
                        by_category[best_category] = []
                    by_category[best_category].append(article)
                    processed_articles.add(article_id)
            
            # Create digest data structure
            digest_data = {
                'user_id': user_id,
                'email': user_prefs.get('email'),
                'categories': {},
                'total_articles': len(articles),
                'generation_date': datetime.now().isoformat(),
                'subject_prefix': '[Daily Digest]' if user_prefs.get('digest_frequency') == 'daily' else '[Weekly Digest]'
            }
            
            # Format articles for email
            total_articles = 0
            for category, category_articles in by_category.items():
                digest_data['categories'][category] = []
                for article in category_articles:
                    email_article = {
                        'id': article.get('id', 0),
                        'title': article.get('title', 'No Title'),
                        'ai_summary': article.get('ai_summary') or article.get('original_summary', '')[:300] + '...' if article.get('original_summary', '') else 'No summary available',
                        'source_link': article.get('source_link', '#'),
                        'author': article.get('author', 'Unknown'),
                        'publication_date': article.get('publication_date', datetime.now().isoformat())
                    }
                    digest_data['categories'][category].append(email_article)
                    total_articles += 1
            
            # Send digest email
            success, message = self.email_manager.deliver_digest_email(user_id, digest_data)
            
            if success:
                logger.info(f"✅ Digest sent successfully to {user_id} ({total_articles} articles)")
                # Update last sent time
                self.update_last_sent_time(user_id)
                return True
            else:
                logger.error(f"❌ Failed to send digest to {user_id}: {message}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending scheduled digest to {user_id}: {e}")
            return False
    
    def update_last_sent_time(self, user_id: str):
        """Update the last sent time for a user."""
        try:
            import sqlite3
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE user_preferences 
                    SET last_digest_sent = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating last sent time for {user_id}: {e}")
    
    def send_daily_digests(self):
        """Send digests to all daily users."""
        logger.info("🌅 Running daily digest job...")
        daily_users = self.get_users_by_frequency('daily')
        
        if not daily_users:
            logger.info("No daily digest users found")
            return
        
        logger.info(f"Found {len(daily_users)} daily digest users")
        success_count = 0
        
        for user in daily_users:
            if self.send_scheduled_digest(user['user_id']):
                success_count += 1
            time.sleep(2)  # Rate limiting between emails
        
        logger.info(f"📊 Daily digest summary: {success_count}/{len(daily_users)} emails sent successfully")
    
    def send_weekly_digests(self):
        """Send digests to all weekly users."""
        logger.info("📅 Running weekly digest job...")
        weekly_users = self.get_users_by_frequency('weekly')
        
        if not weekly_users:
            logger.info("No weekly digest users found")
            return
        
        logger.info(f"Found {len(weekly_users)} weekly digest users")
        success_count = 0
        
        for user in weekly_users:
            if self.send_scheduled_digest(user['user_id']):
                success_count += 1
            time.sleep(2)  # Rate limiting between emails
        
        logger.info(f"📊 Weekly digest summary: {success_count}/{len(weekly_users)} emails sent successfully")
    
    def generate_daily_oneliners(self):
        """Generate daily one-liners for email highlights."""
        logger.info("✨ Running daily one-liner generation job...")
        
        try:
            result = self.oneliner_service.generate_daily_oneliners(oneliners_per_category=10)
            
            if result['total_generated'] > 0:
                logger.info(f"Generated {result['total_generated']} one-liners, saved {result['successful_saves']}")
                
                # Log by category
                for category, count in result['by_category'].items():
                    logger.info(f"  - {category}: {count} one-liners")
                    
                # Clean up old one-liners (keep last 7 days)
                cleaned = self.oneliner_service.cleanup_old_oneliners(days_to_keep=7)
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} old one-liners")
                    
            else:
                logger.info("No new one-liners generated (sufficient content already exists)")
                
            if result['errors']:
                for error in result['errors']:
                    logger.warning(f"One-liner generation error: {error}")
                    
        except Exception as e:
            logger.error(f"Error in daily one-liner generation: {e}")
    
    def setup_schedule(self):
        """Setup the scheduled jobs."""
        # Generate daily one-liners at 6:00 AM (before digests)
        schedule.every().day.at("06:00").do(self.generate_daily_oneliners)
        
        # Daily digests at 8:00 AM
        schedule.every().day.at("08:00").do(self.send_daily_digests)
        
        # Weekly digests on Monday at 9:00 AM
        schedule.every().monday.at("09:00").do(self.send_weekly_digests)
        
        logger.info("📅 Scheduler setup complete:")
        logger.info("   - Daily one-liners: Every day at 6:00 AM")
        logger.info("   - Daily digests: Every day at 8:00 AM")
        logger.info("   - Weekly digests: Every Monday at 9:00 AM")
    
    def start(self):
        """Start the scheduler."""
        self.setup_schedule()
        self.running = True
        
        logger.info("🚀 Digest scheduler started. Press Ctrl+C to stop.")
        
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("🛑 Scheduler stopped by user")
            self.running = False
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            self.running = False
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        logger.info("🛑 Scheduler stopped")
    
    def get_next_runs(self) -> Dict:
        """Get next scheduled run times."""
        jobs = schedule.get_jobs()
        next_runs = {}
        
        for job in jobs:
            next_run = job.next_run
            if next_run:
                job_name = job.job_func.__name__
                next_runs[job_name] = next_run.strftime('%Y-%m-%d %H:%M:%S')
        
        return next_runs


def main():
    """Run the scheduler as a standalone script."""
    print("🌟 News Digest Scheduler")
    print("=" * 40)
    
    scheduler = DigestScheduler()
    
    # Show current users
    daily_users = scheduler.get_users_by_frequency('daily')
    weekly_users = scheduler.get_users_by_frequency('weekly')
    
    print(f"📊 Current users:")
    print(f"   Daily: {len(daily_users)} users")
    print(f"   Weekly: {len(weekly_users)} users")
    print()
    
    if daily_users or weekly_users:
        scheduler.start()
    else:
        print("❌ No users with email addresses found. Add users first:")
        print("   python main.py user add --email user@example.com")


if __name__ == "__main__":
    main()